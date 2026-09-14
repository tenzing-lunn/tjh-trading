"""Engine Room plumbing -- self-populating universe data + JSON-safe wrappers around
the canonical engines (scan.scan_universe, xsect's momentum pipeline, alpaca_paper's
account calls) so api_server.py can serve them live to the browser.

Why this exists: realdata/ is gitignored (vendor terms), so the deployed backend has
no CSVs for the 30-stock universe. ensure_universe_data() fills data_cache/ on demand
-- Alpaca first (the team's decided stack), batched yfinance as the fallback -- and
records WHICH source served each ticker, so the web app's data panel shows the truth
about provenance instead of a hand-wave.

Hard rule (same as export_results.py): no new backtest math here. This module only
fetches data, calls the existing engines, and shapes their output into JSON.
"""
import glob
import os
import threading
import time
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from data import load_csv
from fetch_universe import UNIVERSE, BENCHMARK, SECTORS
from metrics import compute_metrics
from scan import scan_universe, _verdict, CANDIDATES, N_FOLDS, MIN_TRADES_PER_FOLD
from xsect import (load_panel, target_weights, run_panel, _first_active,
                   month_end_mask, momentum_12_1, robustness, sweep,
                   significance_vs_ew, panel_verdict,
                   EXCLUDE, TOP_N, ETF_COST)

CACHE_DIR = 'data_cache'
TTL_SECONDS = 30 * 60          # rapid repeat page loads must not re-hit any vendor
FETCH_YEARS = 8                # same window as fetch_universe.py / fetch_alpaca.py


def _load_dotenv(path='.env'):
    """Minimal .env loader (stdlib only) so the local API picks up the gitignored Alpaca
    keys without the user exporting them by hand. Never overrides real env vars -- on
    Render the dashboard env vars win and this is a no-op (no .env is deployed)."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

# Module-level cache: manifest + when it was built. One fetch at a time (lock) so a
# burst of parallel first requests can't trigger duplicate vendor pulls.
_lock = threading.Lock()
_state = {'built_at': None, 'manifest': None}


# ---- JSON safety -------------------------------------------------------------------
def json_safe(obj):
    """Recursively convert numpy scalars to Python and NaN to None (NaN isn't JSON)."""
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        obj = float(obj)
    if isinstance(obj, float):
        return None if obj != obj else obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


# ---- data sourcing -----------------------------------------------------------------
def _local_path(sym):
    """Existing CSV for a symbol: realdata/ (local dev) beats data_cache/ (fetched)."""
    for d, src in (('realdata', 'realdata'), (CACHE_DIR, 'cache')):
        p = os.path.join(d, f'{sym.lower()}.csv')
        if os.path.exists(p):
            return p, src
    return None, None


def _save(sym, frame):
    """Write one OHLCV frame to data_cache/ in the harness format (same columns as
    export_results.fetch_yf writes, whichever vendor produced it)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    frame = frame[['open', 'high', 'low', 'close', 'volume']].dropna(how='all')
    path = os.path.join(CACHE_DIR, f'{sym.lower()}.csv')
    frame.to_csv(path, index_label='date')
    return path


def _alpaca_keys():
    return os.getenv('APCA_API_KEY_ID'), os.getenv('APCA_API_SECRET_KEY')


def _fetch_alpaca(symbols):
    """One batched StockBarsRequest for all `symbols` (same client/adjustment settings
    as fetch_alpaca.py: Adjustment.ALL, SIP feed for full-market depth). Returns {sym: path}
    for every symbol Alpaca actually served; raises only if the whole request fails."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
    from alpaca.data.enums import Adjustment, DataFeed

    key, secret = _alpaca_keys()
    client = StockHistoricalDataClient(key, secret)
    start = (datetime.utcnow() - timedelta(days=365 * FETCH_YEARS)).strftime('%Y-%m-%d')
    end = (datetime.utcnow() - timedelta(minutes=16)).strftime('%Y-%m-%d')
    req = StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day,
                           start=start, end=end, feed=DataFeed.SIP, adjustment=Adjustment.ALL)
    df = client.get_stock_bars(req).df
    out = {}
    if df is None or df.empty:
        return out
    df = df.reset_index()
    df['date'] = df['timestamp'].dt.tz_convert(None).dt.normalize()
    for sym, grp in df.groupby('symbol'):
        frame = grp.set_index('date')[['open', 'high', 'low', 'close', 'volume']].sort_index()
        if len(frame):
            out[sym] = _save(sym, frame)
    return out


def _fetch_yfinance(symbols):
    """Batched, threaded yf.download for `symbols` (same pattern as fetch_universe.main
    -- one request, not N sequential ones). Returns {sym: path} for served symbols."""
    import yfinance as yf
    data = yf.download(list(symbols), period=f'{FETCH_YEARS}y', interval='1d',
                       auto_adjust=True, group_by='ticker', progress=False, threads=True)
    out = {}
    if data is None or data.empty:
        return out
    for sym in symbols:
        try:
            frame = data[sym] if len(symbols) > 1 else data
            frame = frame.rename(columns=str.lower).dropna(how='all')
            if len(frame):
                out[sym] = _save(sym, frame)
        except Exception:
            continue                                   # recorded as failed by the caller
    return out


def _describe(sym, path, source):
    """Per-ticker manifest entry, reading the row count / date range off the CSV."""
    entry = {'ticker': sym, 'sector': SECTORS.get(sym, '?'), 'source': source,
             'rows': None, 'start': None, 'end': None, 'ok': False, 'error': None}
    try:
        df = load_csv(path, warn=False)
        entry.update(rows=int(len(df)),
                     start=str(df.index[0].date()), end=str(df.index[-1].date()),
                     ok=len(df) > 0)
        if not len(df):
            entry['error'] = 'file exists but has no usable rows'
    except Exception as e:
        entry['error'] = str(e)
    return entry


def ensure_universe_data(force=False):
    """Make sure every UNIVERSE + BENCHMARK ticker has a local CSV, fetching what is
    missing (Alpaca first if keys are set, batched yfinance as fallback). Returns
    {'tickers': [manifest...], 'summary': {...}}. Cached for TTL_SECONDS; force=True
    bypasses the TTL and re-fetches everything not served from realdata/."""
    with _lock:
        now = time.time()
        if (not force and _state['manifest'] is not None
                and now - _state['built_at'] < TTL_SECONDS):
            return _result(_state['manifest'], now - _state['built_at'])

        syms = BENCHMARK + UNIVERSE
        manifest, need = [], []
        for sym in syms:
            path, src = _local_path(sym)
            if path and src == 'realdata':             # local dev data always wins
                manifest.append(_describe(sym, path, 'realdata'))
            elif path and not force:                   # previously fetched this process/dyno
                manifest.append(_describe(sym, path, 'cache'))
            else:
                need.append(sym)

        if need:
            served = {}
            alpaca_error = None
            key, secret = _alpaca_keys()
            if key and secret:
                try:
                    served = _fetch_alpaca(need)
                except Exception as e:                 # whole-request failure -> fall back
                    alpaca_error = str(e)
            for sym, path in served.items():
                manifest.append(_describe(sym, path, 'alpaca'))

            missing = [s for s in need if s not in served]
            if missing:
                yf_served, yf_error = {}, None
                try:
                    yf_served = _fetch_yfinance(missing)
                except Exception as e:
                    yf_error = str(e)
                for sym in missing:
                    if sym in yf_served:
                        manifest.append(_describe(sym, yf_served[sym], 'yfinance-fallback'))
                    else:
                        err = yf_error or alpaca_error or 'no data returned by any vendor'
                        manifest.append({'ticker': sym, 'sector': SECTORS.get(sym, '?'),
                                         'source': 'none', 'rows': None, 'start': None,
                                         'end': None, 'ok': False, 'error': err})

        order = {s: i for i, s in enumerate(syms)}
        manifest.sort(key=lambda m: order.get(m['ticker'], 99))
        _state['manifest'], _state['built_at'] = manifest, time.time()
        return _result(manifest, 0.0)


def _result(manifest, age):
    ok = [m for m in manifest if m['ok']]
    return json_safe({
        'tickers': manifest,
        'summary': {
            'n_ok': len(ok), 'n_failed': len(manifest) - len(ok),
            'cache_age_seconds': round(age),
            'ttl_seconds': TTL_SECONDS,
            'source': f'daily bars, {FETCH_YEARS}y, split/dividend-adjusted '
                      '(Alpaca SIP feed first, yfinance fallback)',
            'alpaca_configured': bool(_alpaca_keys()[0] and _alpaca_keys()[1]),
        },
    })


def _paths():
    """(stock_paths, spy_path) for whatever is on disk right now -- realdata/ preferred,
    data_cache/ otherwise. Call ensure_universe_data() first."""
    stock_paths, spy_path = [], None
    for sym in UNIVERSE:
        p, _ = _local_path(sym)
        if p:
            stock_paths.append(p)
    for sym in BENCHMARK:
        p, _ = _local_path(sym)
        if p:
            spy_path = p
    return stock_paths, spy_path


# ---- live wide scan ------------------------------------------------------------------
def run_scan(force=False):
    """ensure data -> scan.scan_universe (unmodified) -> JSON-safe rows with every gate."""
    universe = ensure_universe_data(force)
    stock_paths, spy_path = _paths()
    if not stock_paths:
        return {'error': 'no universe data available (all vendor fetches failed)',
                'universe': universe}
    benchmark = load_csv(spy_path, warn=False)['close'] if spy_path else None

    t0 = time.time()
    rows = scan_universe(stock_paths, benchmark=benchmark)
    elapsed = time.time() - t0

    rows.sort(key=lambda r: (r['metrics']['total_return']
                             if r['metrics']['total_return'] == r['metrics']['total_return']
                             else -1e9), reverse=True)
    for r in rows:
        r['verdict'] = _verdict(r)
        r['ticker'] = r['ticker'].upper()
    n_edge = sum(r['clean'] for r in rows)
    n_suspect = sum(r['survives_gate2'] and not r['clean'] for r in rows)
    return json_safe({
        'summary': {
            'n_backtests': len(rows),
            'n_tickers': len({r['ticker'] for r in rows}),
            'strategies': list(CANDIDATES.keys()),
            'n_edge': n_edge, 'n_suspect': n_suspect,
            'n_dead': len(rows) - n_edge - n_suspect,
            'elapsed_seconds': round(elapsed, 2),
            'n_folds': N_FOLDS, 'min_trades_per_fold': MIN_TRADES_PER_FOLD,
            'cost_regime': 'liquid ETF (3/1 bps), walk-forward OOS',
            'has_spy_benchmark': benchmark is not None,
        },
        'rows': rows,
    })


# ---- live Thesis 001 (cross-sectional momentum) ---------------------------------------
def run_momentum(force=False):
    """ensure data -> xsect's exact pipeline (target_weights/run_panel/robustness/sweep)
    -> JSON payload with all baselines, per-year split, PSR, regimes, sweep, verdicts."""
    universe = ensure_universe_data(force)
    stock_paths, spy_path = _paths()
    stock_paths = [p for p in stock_paths
                   if os.path.splitext(os.path.basename(p))[0] not in EXCLUDE]
    if not stock_paths:
        return {'error': 'no universe data available (all vendor fetches failed)',
                'universe': universe}

    t0 = time.time()
    panel = load_panel(stock_paths)
    res = _first_active(run_panel(panel, target_weights(panel)))
    window = res.index

    # Baseline 1: hold SPY over the identical live window, same cost model.
    spy_close_full = load_csv(spy_path, warn=False)['close'] if spy_path else None
    spy_m = None
    if spy_close_full is not None:
        from backtest import run_backtest
        spy = spy_close_full.reindex(window).dropna()
        _, spy_m = run_backtest(spy, pd.Series(1.0, index=spy.index), ETF_COST)

    # Baseline 2: equal-weight ALL eligible names (same construction as xsect.main).
    scores = momentum_12_1(panel)
    rebal = month_end_mask(panel.index)
    ew = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for t in panel.index[rebal]:
        row = scores.loc[t].dropna()
        if len(row) < TOP_N:
            continue
        wt = pd.Series(0.0, index=panel.columns)
        wt[row.index] = 1.0 / len(row)
        ew.loc[t] = wt
    ew_res = _first_active(run_panel(panel, ew.ffill().fillna(0.0))).reindex(window).dropna()

    # Baseline 3: random top-N picks each month, same machinery, fixed seed.
    rng = np.random.default_rng(1)
    rand_res = _first_active(run_panel(
        panel, target_weights(panel, picker=lambda row: rng.choice(
            row.index, size=TOP_N, replace=False)))).reindex(window).dropna()

    m, m_ew, m_rand = compute_metrics(res), compute_metrics(ew_res), compute_metrics(rand_res)

    per_year = []
    for yr, g in res.groupby(res.index.year):
        ge = ew_res.reindex(g.index).dropna()
        per_year.append({'year': int(yr),
                         'momentum': float((1 + g['net']).prod() - 1),
                         'ew_universe': float((1 + ge['net']).prod() - 1) if len(ge) else None})

    rob = robustness(res, spy_close_full, ew_res=ew_res)
    sw = sweep(panel)
    n_beat = sum(s['beats_ew'] for s in sw)         # display only -- sign of a margin, not breadth
    n_sig = sum(s['t_active'] >= 2 for s in sw)     # the honest count: monthly-active t >= 2

    # The verdict is decided in exactly one place (xsect.panel_verdict), so the live Engine
    # Room cannot drift from the CLI's answer: raw bars AND the edge over the EW-universe
    # being statistically real (t >= 2) AND no robustness flag.
    sig = significance_vs_ew(res, ew_res, panel)
    pv = panel_verdict(m, m_ew, m_rand, spy_m, rob['flags'], sig)
    elapsed = time.time() - t0

    return json_safe({
        'spec': f'12-1 cross-sectional momentum, monthly, top {TOP_N} of '
                f'{panel.shape[1]} stocks, long-only, equal weight, n_trials=1',
        'window': [str(window[0].date()), str(window[-1].date())],
        'bars': int(len(window)),
        'n_names': int(panel.shape[1]),
        'portfolios': {
            'momentum': m, 'ew_universe': m_ew, 'random': m_rand, 'spy': spy_m,
        },
        'per_year': per_year,
        'probabilistic_sharpe': rob['psr'],
        'psr_months': rob['months'],
        'regime_split': rob['regimes'],
        'red_flags': rob['flags'],
        'sweep': sw,
        'sweep_beats_ew': f'{n_beat}/{len(sw)}',
        'sweep_significant': f'{n_sig}/{len(sw)}',
        'verdict': pv,          # survives / status / beats_* / t_active / ci / pct_won
        'caveats': ["universe is survivorship-biased (today's liquid names) -- "
                    "'beats EW universe' is the honest bar, not the raw return",
                    'single history, no parameter search (n_trials=1, nothing to '
                    'overfit, but only one draw)'],
        'elapsed_seconds': round(elapsed, 2),
    })


# ---- live Alpaca paper account ---------------------------------------------------------
def alpaca_status():
    """Paper-account snapshot via the same TradingClient calls as alpaca_paper.status().
    Never raises for the expected states: missing keys / missing package / API failure
    all come back as structured JSON so the UI can say what happened."""
    key, secret = _alpaca_keys()
    if not key or not secret:
        return {'configured': False,
                'reason': 'APCA_API_KEY_ID / APCA_API_SECRET_KEY not set on this backend'}
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        return {'configured': False,
                'reason': 'alpaca-py is not installed on this backend'}
    try:
        client = TradingClient(key, secret, paper=True)   # paper=True is non-negotiable
        a = client.get_account()
        positions = client.get_all_positions()
    except Exception as e:
        return {'configured': True, 'ok': False, 'error': str(e)}
    return json_safe({
        'configured': True, 'ok': True,
        'account': {
            # public web surface: mask the account number, show only enough to identify it
            'account_number': f'···{str(a.account_number)[-4:]}',
            'status': getattr(a.status, 'value', str(a.status)),
            'equity': float(a.equity), 'cash': float(a.cash),
            'buying_power': float(a.buying_power),
        },
        'positions': [{
            'symbol': p.symbol, 'qty': float(p.qty),
            'avg_entry_price': float(p.avg_entry_price),
            'market_value': float(p.market_value),
            'unrealized_pl': float(p.unrealized_pl),
        } for p in positions],
    })
