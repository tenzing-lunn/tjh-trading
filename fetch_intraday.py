"""Fetch Alpaca SIP 1-minute bars for SPY + QQQ + the 30-name core, 2016-01 -> now
(plan/14 I1.1).

Run LOCALLY (needs internet + your keys in .env or the environment):

    python3 fetch_intraday.py                # SPY + QQQ + the 30-name core
    python3 fetch_intraday.py TQQQ SOFI       # extra tickers appended to the list

## Point-in-time rule (IQF design)
A bar stamped `timestamp` covers [timestamp, timestamp + 1 minute) and is only fully
formed -- and therefore only knowable to a strategy -- at `timestamp + 1 minute`.
Downstream engines must never act on a bar before that instant (this is on top of, not
instead of, plan/14's separate 15-minute delayed-feed simulation for the "live" case).

## Storage
One parquet per symbol-month: intraday/<SYM>/<YYYY-MM>.parquet, columns
timestamp (UTC, bar START), open, high, low, close, volume, trade_count, vwap, regular
(bool: 09:30 <= bar start < 16:00 America/New_York, DST-aware). Pre/post-market bars are
kept, just flagged. A manifest at intraday/manifest.json records provenance per
symbol-month (rows, regular_rows, first/last timestamp, retrieval_time, source, feed,
adjustment, status) so downstream code can tell what it's looking at without re-deriving it.

## Resumability
A past symbol-month recorded as "ok" is skipped only if its parquet still exists.
Empty months are retried on the next run; a transient empty response is not permanent.
The current (in-progress) calendar month is always refetched, since it's incomplete by
definition. Writes go to a temp file then get renamed, so a crashed run never leaves a
half-written parquet.

## Rate limiting
Throttle each HTTP request, including SDK pagination and retries, to under 200/min.
Only run one fetch process at a time: this limiter is local to this process.
"""
import ast
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment, DataFeed

OUT_DIR = "intraday"
MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")
START = datetime(2016, 1, 1, tzinfo=timezone.utc)
MIN_CALL_INTERVAL = 0.35   # <=172 requests/min, including pages and retries


class ThrottledStockClient(StockHistoricalDataClient):
    """Rate limit the SDK's actual HTTP boundary, not just top-level month calls."""
    _last_request = None

    def _one_request(self, *args, **kwargs):
        if self._last_request is not None:
            time.sleep(max(0, MIN_CALL_INTERVAL - (time.monotonic() - self._last_request)))
        self._last_request = time.monotonic()
        return super()._one_request(*args, **kwargs)


def _load_dotenv(path=".env"):
    """Minimal .env loader (stdlib only), never overrides real env vars. Never prints
    or logs the values it loads."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def universe_symbols():
    """SPY + QQQ + the 30-name core from fetch_universe.SECTORS, without importing
    fetch_universe (which drags in yfinance, not installed here). Parses the SECTORS
    dict literal out of the source with ast instead."""
    with open("fetch_universe.py") as f:
        tree = ast.parse(f.read())
    sectors = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "SECTORS" for t in node.targets
        ):
            sectors = ast.literal_eval(node.value)
            break
    if sectors is None:
        sys.exit("Could not find SECTORS in fetch_universe.py")
    core = [sym for sym, sector in sectors.items() if sector != "Benchmark"]
    return ["SPY", "QQQ"] + core


def month_starts(start, end):
    """Yield UTC month-boundary datetimes from `start`'s month through `end`'s month,
    inclusive -- i.e. len(result) - 1 months, each (month_starts[i], month_starts[i+1])."""
    cur = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    out = [cur]
    while cur < end:
        year, month = cur.year + (cur.month // 12), (cur.month % 12) + 1
        cur = cur.replace(year=year, month=month)
        out.append(cur)
    return out


def add_regular_flag(df):
    """True for bars whose START falls in 09:30 <= t < 16:00 America/New_York (DST-aware)."""
    local = df["timestamp"].dt.tz_convert("America/New_York")
    t = local.dt.hour * 60 + local.dt.minute
    return (t >= 9 * 60 + 30) & (t < 16 * 60)


def fetch_month(client, symbol, month_start, month_end, retries=5):
    """One symbol-month, with our own retry/backoff on top of the client's built-in one.
    Never silently skips a rate-limit error -- always retries or raises."""
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=month_start,
        end=month_end,
        feed=DataFeed.SIP,
        adjustment=Adjustment.ALL,
    )
    delay = 5
    for attempt in range(retries):
        try:
            bars = client.get_stock_bars(req)
            return bars.df
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "too many requests" in msg:
                print(f"    rate limited, backing off {delay}s (attempt {attempt+1}/{retries})")
                time.sleep(delay)
                delay = min(delay * 2, 60)
                continue
            raise
    raise RuntimeError(f"{symbol} {month_start:%Y-%m}: exhausted retries on rate limiting")


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH) as f:
            return json.load(f)
    return {}


def save_manifest(manifest):
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = MANIFEST_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True, default=str)
    os.replace(tmp, MANIFEST_PATH)


def fetch_symbol(client, symbol, manifest, now_cutoff):
    sym_dir = os.path.join(OUT_DIR, symbol)
    os.makedirs(sym_dir, exist_ok=True)
    manifest.setdefault(symbol, {})

    bounds = month_starts(START, now_cutoff)
    current_month_key = now_cutoff.strftime("%Y-%m")

    for month_start, month_end_bound in zip(bounds[:-1], bounds[1:]):
        key = month_start.strftime("%Y-%m")
        month_end = min(month_end_bound, now_cutoff)
        is_current = key == current_month_key

        existing = manifest[symbol].get(key)
        path = os.path.join(sym_dir, f"{key}.parquet")
        if (not is_current and existing and existing.get("status") == "ok"
                and os.path.isfile(path)):
            print(f"  {symbol} {key}: skip (already {existing['status']})")
            continue

        print(f"  {symbol} {key}: fetching...")
        df = fetch_month(client, symbol, month_start, month_end)
        retrieval_time = datetime.now(timezone.utc).isoformat()

        if df is None or df.empty:
            if existing and existing.get("status") == "ok":
                raise RuntimeError(f"{symbol} {key}: empty refresh; keeping previous cache")
            manifest[symbol][key] = {
                "rows": 0, "regular_rows": 0,
                "first": None, "last": None,
                "retrieval_time": retrieval_time,
                "source": "alpaca", "feed": "sip", "adjustment": "all",
                "status": "empty",
            }
            print(f"  {symbol} {key}: 0 rows -> empty")
            save_manifest(manifest)
            continue

        df = df.reset_index()
        if "symbol" in df.columns:
            df = df.drop(columns=["symbol"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        # API endpoints can be inclusive; keep file partitions disjoint.
        df = df[(df["timestamp"] >= month_start) & (df["timestamp"] < month_end)]
        if df.empty or df["timestamp"].duplicated().any():
            raise ValueError(f"{symbol} {key}: empty partition or duplicate timestamps")
        df["regular"] = add_regular_flag(df)
        cols = ["timestamp", "open", "high", "low", "close", "volume",
                "trade_count", "vwap", "regular"]
        df = df[[c for c in cols if c in df.columns]].sort_values("timestamp")

        path = os.path.join(sym_dir, f"{key}.parquet")
        tmp_path = path + ".tmp"
        df.to_parquet(tmp_path, index=False)
        os.replace(tmp_path, path)

        manifest[symbol][key] = {
            "rows": int(len(df)),
            "regular_rows": int(df["regular"].sum()),
            "first": df["timestamp"].min().isoformat(),
            "last": df["timestamp"].max().isoformat(),
            "retrieval_time": retrieval_time,
            "source": "alpaca", "feed": "sip", "adjustment": "all",
            "status": "ok",
        }
        print(f"  {symbol} {key}: {len(df)} rows ({int(df['regular'].sum())} regular)")
        save_manifest(manifest)  # persist incrementally so a crash loses at most one month


def main():
    _load_dotenv()
    key, secret = os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY (.env or environment) first.")

    extra = [s.upper() for s in sys.argv[1:]]
    base = universe_symbols()
    symbols = base + [s for s in extra if s not in base]

    client = ThrottledStockClient(key, secret)
    now_cutoff = datetime.now(timezone.utc) - timedelta(minutes=16)
    manifest = load_manifest()

    print(f"Fetching {len(symbols)} symbols, {START:%Y-%m} -> {now_cutoff:%Y-%m-%d %H:%M} UTC")
    for symbol in symbols:
        fetch_symbol(client, symbol, manifest, now_cutoff)

    save_manifest(manifest)
    print("Done.")


if __name__ == "__main__":
    main()
