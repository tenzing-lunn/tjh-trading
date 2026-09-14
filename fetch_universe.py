"""Fetch a curated LIQUID universe of daily bars into realdata/ for the wide scan.

Run LOCALLY (needs internet + `pip install yfinance`):
    python3 fetch_universe.py                 # the whole curated universe
    python3 fetch_universe.py AAPL MSFT       # just these (added to the universe)

Split/dividend-ADJUSTED closes (auto_adjust=True). Yahoo data is redistribution-restricted,
so realdata/ is gitignored: we keep the fetch CODE, not the data. Re-run any time to
refresh; scan.py/xsect.py then pick up every realdata/*.csv automatically.

## Universe size: 30, not ~100 (slimmed 2026-07-06)
We ran a ~97-name broad scan (see plan/02-verdict-log) and it did its job -- 0 EDGE?,
proving liquid daily-bar timing mostly doesn't work. But 100 names is more than a 3-person
club needs to prototype on, and it hid the signal in noise. This is a deliberately SMALL,
BORING, diversified core of 30 megacaps across 6 sectors -- no penny/pre-IPO junk (nio,
sofi, plug, snap all cut), no leverage (tqqq cut), one clean benchmark (SPY; qqq/dia/iwm/vti
cut). Quality over quantity: easier to reason about, faster to iterate, same engine.
Broaden again later only if Tenzing approves a bigger list for a specific reason.
"""
import os
import sys
import yfinance as yf

UNIVERSE = [
    # Tech / semis (10)
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "ADBE", "CRM", "ORCL",
    # Financials (5)
    "JPM", "BAC", "GS", "MA", "V",
    # Healthcare (5)
    "UNH", "JNJ", "LLY", "ABBV", "MRK",
    # Consumer (7)
    "WMT", "COST", "HD", "PG", "KO", "MCD", "NKE",
    # Energy / industrial (3)
    "XOM", "CVX", "CAT",
]
# Benchmark, fetched separately so spy.csv always exists for scan.py/xsect.py's SPY
# comparison, without counting toward the 30-name stock panel.
BENCHMARK = ["SPY", "MTUM"]

# Ticker -> sector, the shared source of truth for any grouping (engine_api.py /
# the web app's data panel). Keep in sync with the UNIVERSE comment blocks above.
SECTORS = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "GOOGL": "Tech", "AMZN": "Tech",
    "META": "Tech", "AVGO": "Tech", "ADBE": "Tech", "CRM": "Tech", "ORCL": "Tech",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    "MA": "Financials", "V": "Financials",
    "UNH": "Healthcare", "JNJ": "Healthcare", "LLY": "Healthcare",
    "ABBV": "Healthcare", "MRK": "Healthcare",
    "WMT": "Consumer", "COST": "Consumer", "HD": "Consumer", "PG": "Consumer",
    "KO": "Consumer", "MCD": "Consumer", "NKE": "Consumer",
    "XOM": "Energy/Industrial", "CVX": "Energy/Industrial", "CAT": "Energy/Industrial",
    "SPY": "Benchmark", "MTUM": "Benchmark",
}


def save(sym, frame):
    """Normalise one ticker's OHLCV frame to harness format and write realdata/<sym>.csv."""
    frame = frame[["Open", "High", "Low", "Close", "Volume"]].dropna(how="all")
    frame.columns = ["open", "high", "low", "close", "volume"]
    frame.to_csv(f"realdata/{sym.lower()}.csv")
    return len(frame)


def main():
    base = BENCHMARK + UNIVERSE
    syms = base + [s.upper() for s in sys.argv[1:] if s.upper() not in base]
    os.makedirs("realdata", exist_ok=True)
    # One batched, threaded request is gentler on Yahoo's rate limit than N sequential ones.
    data = yf.download(syms, period="8y", interval="1d", auto_adjust=True,
                       group_by="ticker", progress=False, threads=True)
    ok = fail = 0
    for s in syms:
        try:
            frame = data[s] if len(syms) > 1 else data
            n = save(s, frame)
            print(f"  ok   {s:6s} {n:5d} rows")
            ok += 1
        except Exception as e:                     # missing ticker / empty frame
            print(f"  FAIL {s:6s} {e}")
            fail += 1
    print(f"\n{ok} saved, {fail} failed -> realdata/  (gitignored; run scan.py next)")


if __name__ == "__main__":
    main()
