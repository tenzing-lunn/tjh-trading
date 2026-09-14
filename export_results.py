"""Phase 1 -- export web-ready results from the CANONICAL harness.

The web app must display the truth without re-implementing any strategy or cost
math in JavaScript. This script is the one bridge: it RUNS the existing engine
(strategies / backtest / costs / metrics / walkforward) and serializes the output
to a single JSON file. No alpha logic lives here -- only reading and shaping.

    python3 export_results.py                  # synthetic fixture -> exports/synthetic.results.json
    python3 export_results.py realdata/tqqq.csv   # real ticker   -> exports/tqqq.results.json

Schema (schema_version 1): meta, data_quality, cost_regimes, strategies
(label/description/positions/trades/equity), metrics[strategy][regime], and
walk_forward[name] (out-of-sample, params-per-fold). See plan/06-engineering-plan.md.
"""
import os
import sys
import json
import datetime as dt

import numpy as np
import pandas as pd

from data import synthetic_ohlcv, load_csv, quality_report
from costs import CostModel
from backtest import run_backtest
from metrics import compute_metrics, infer_ppy
from strategies import (buy_and_hold, random_strategy, sma_crossover,
                        mean_reversion, kronos_signal)
from walkforward import walk_forward
from diagnostics import diagnose, config_sharpes
from run import load_kronos_forecast

SCHEMA_VERSION = 1

# Cost regimes, mirrored from run.py so the export and the CLI tell the same story.
REGIMES = {
    'frictionless': ('FRICTIONLESS (the lie)', CostModel(spread_bps=0,   slippage_bps=0)),
    'liquid_etf':   ('Liquid ETF (SPY-like)',  CostModel(spread_bps=3,   slippage_bps=1)),
    'cheap_option': ('Cheap option spread',    CostModel(spread_bps=300, slippage_bps=50)),
}
DISPLAY_REGIME = 'liquid_etf'   # the equity curve the app charts: the honest one for stocks

# Strategy registry: factory + plain-English description for non-coders.
STRATEGIES = {
    'buy_and_hold': dict(
        fn=lambda px: buy_and_hold(px), label='Buy & hold', tunable=False,
        description='Always fully long. The benchmark every active strategy must beat.'),
    'random': dict(
        fn=lambda px: random_strategy(px, seed=1), label='Random', tunable=False,
        description='Coin-flip long/flat. The noise floor: beat this or you have nothing.'),
    'sma_20_100': dict(
        fn=lambda px: sma_crossover(px, fast=20, slow=100), label='SMA crossover (20/100)',
        tunable=True,
        description='Long when the 20-bar average is above the 100-bar average; flat '
                    'otherwise. Classic trend-following.'),
    'meanrev_20_1': dict(
        fn=lambda px: mean_reversion(px, lookback=20, entry_z=1.0),
        label='Mean reversion (z-score, 20/1.0)', tunable=True,
        description='Long when price is >1 std-dev below its 20-bar mean, short when >1 '
                    'above. Bets the price snaps back.'),
}


def series(s, nd):
    """Round + None-ify NaN so the JSON is small and valid (NaN is not legal JSON)."""
    return [None if (v != v) else round(float(v), nd) for v in s]


def trades_from_positions(pos, dates, px):
    """A trade = the held position changing. Emit one marker per change with the
    price at that bar, so the app can plot entries/exits on the price chart."""
    prev = pos.shift(1).fillna(0.0)
    changed = (pos != prev)
    out = []
    for d, frm, to, p in zip(dates[changed], prev[changed], pos[changed], px[changed]):
        out.append({'date': d.strftime('%Y-%m-%d'),
                    'from': round(float(frm), 3), 'to': round(float(to), 3),
                    'price': round(float(p), 4)})
    return out


def metrics_json(m):
    return {k: (None if (v != v) else round(float(v), 6)) for k, v in m.items()}


def json_safe(v):
    """Recursively round floats and turn NaN into None so nested diagnostics (per-year,
    regime split, deflated Sharpe) serialize to valid JSON. Mirrors metrics_json for
    the nested structures compute_metrics/diagnostics.py already produced."""
    if isinstance(v, dict):
        return {k: json_safe(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [json_safe(x) for x in v]
    if hasattr(v, 'item'):                 # numpy scalar -> python scalar
        v = v.item()
    if isinstance(v, float):
        return None if v != v else round(v, 6)
    return v


def fetch_yf(symbol, period='8y'):
    """Live-fetch OHLCV for an arbitrary ticker via yfinance and cache it locally,
    so 'pick any ticker' works on the deployed backend without committing vendor
    data. Raises a clear error if yfinance isn't installed (it's an optional dep)."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError(
            f"'{symbol}' is not a local CSV and yfinance is not installed. "
            f"Install it (pip install yfinance) or add realdata/{symbol.lower()}.csv.")
    raw = yf.download(symbol, period=period, auto_adjust=True, progress=False)
    if raw is None or raw.empty:
        raise RuntimeError(f"yfinance returned no data for '{symbol}'.")
    if isinstance(raw.columns, pd.MultiIndex):            # yf returns a column MultiIndex
        raw.columns = raw.columns.get_level_values(0)
    df = raw.rename(columns=str.lower)[['open', 'high', 'low', 'close', 'volume']]
    os.makedirs('data_cache', exist_ok=True)
    df.to_csv(os.path.join('data_cache', f'{symbol.lower()}.csv'),
              index_label='date')
    return df


def resolve_data(spec):
    """Turn a request (None/'synthetic', a CSV path, a local ticker, or a live
    symbol) into (df, name, source, data_quality, forecast). The single place the
    app decides WHERE data comes from."""
    if spec in (None, '', 'synthetic', 'SYNTHETIC'):
        df = synthetic_ohlcv(n=1500, kappa=0.04)
        dq = [{'level': 'info', 'code': 'synthetic',
               'message': 'Synthetic Ornstein-Uhlenbeck fixture with an edge baked in '
                          '(kappa=0.04). Use only to show the pipeline — real markets are '
                          'closer to kappa=0 (no edge).'}]
        return df, 'synthetic', 'synthetic:OU(kappa=0.04) — NOT market data', dq, None

    path = None
    if os.path.exists(spec):
        path = spec
    else:
        for cand in (os.path.join('realdata', f'{spec.lower()}.csv'),
                     os.path.join('data_cache', f'{spec.lower()}.csv')):
            if os.path.exists(cand):
                path = cand
                break
    if path:
        df = load_csv(path)
        name = os.path.splitext(os.path.basename(path))[0]
        return df, name, f'local:{path}', quality_report(path), load_kronos_forecast(path)

    df = fetch_yf(spec)                                   # live fetch (caches to data_cache/)
    cached = os.path.join('data_cache', f'{spec.lower()}.csv')
    df = load_csv(cached)
    return df, spec.lower(), f'yfinance:{spec.upper()}', quality_report(cached), None


def build_payload(df, name, source, dq, forecast=None, display_cost=None):
    """Build the results.json payload from already-resolved data. Shared by the CLI
    and the API so they cannot drift. `display_cost` (a CostModel) overrides the
    charted/verdict regime, which is how the app does live cost tweaking; the three
    standard regimes are always included for the comparison table."""
    px = df['close'].astype(float)
    dates = px.index

    regimes = dict(REGIMES)
    if display_cost is not None:
        regimes['custom'] = (
            f'Custom ({display_cost.spread_bps:g}/{display_cost.slippage_bps:g} bps)',
            display_cost)
        display_key = 'custom'
    else:
        display_key = DISPLAY_REGIME
    display_cm = regimes[display_key][1]

    strat_specs = dict(STRATEGIES)
    if forecast is not None:
        strat_specs['kronos'] = dict(
            fn=lambda px: kronos_signal(px, forecast=forecast, threshold=0.0),
            label='Kronos (zero-shot)', tunable=True,
            description='Position from a cached Kronos next-bar return forecast '
                        '(long if predicted up, short if down).')

    result = {
        'schema_version': SCHEMA_VERSION,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'meta': {
            'name': name, 'source': source, 'bars': int(len(px)),
            'start': dates[0].strftime('%Y-%m-%d'), 'end': dates[-1].strftime('%Y-%m-%d'),
            'periods_per_year': infer_ppy(px.index),
            'display_regime': display_key,
        },
        'data_quality': dq,
        'cost_regimes': {k: {'label': lbl, 'spread_bps': cm.spread_bps,
                             'slippage_bps': cm.slippage_bps}
                         for k, (lbl, cm) in regimes.items()},
        'prices': {'dates': [d.strftime('%Y-%m-%d') for d in dates],
                   'close': series(px, 4)},
        'strategies': {},
        'metrics': {},
        'walk_forward': {},
    }

    for sname, spec in strat_specs.items():
        pos = spec['fn'](px).reindex(dates).fillna(0.0).clip(-1, 1)
        # Equity curve charted by the app: gross vs net under the display regime.
        out_disp, _ = run_backtest(px, pos, display_cm)
        result['strategies'][sname] = {
            'label': spec['label'], 'description': spec['description'],
            'tunable': spec['tunable'],
            'positions': series(pos, 3),
            'trades': trades_from_positions(pos, dates, px),
            'equity_regime': display_key,
            'equity': {'gross': series((1 + out_disp['gross']).cumprod(), 6),
                       'net':   series(out_disp['equity'], 6)},
        }
        # Metrics for every cost regime -> the cost-comparison table.
        result['metrics'][sname] = {}
        for rk, (_, cm) in regimes.items():
            _, m = run_backtest(px, pos, cm)
            result['metrics'][sname][rk] = metrics_json(m)

    # Out-of-sample walk-forward: params chosen on TRAIN only, scored on unseen TEST.
    mr_grid = [{'lookback': lb, 'entry_z': z}
               for lb in (10, 20, 40) for z in (0.5, 1.0, 1.5, 2.0)]
    mr_factory = lambda p: (lambda prices: mean_reversion(prices, **p))
    combined, chosen = walk_forward(px, mr_factory, mr_grid, display_cm, n_folds=5)
    # Robustness panel (5): deflated Sharpe (best-of-N discount), per-year, regime split
    # (tagged by THIS ticker's own trend), and plain-English red flags. Same diagnostics.py
    # the scan + verdict log consume, so the per-ticker view tells the identical story.
    mr_diag = diagnose(combined, len(mr_grid), benchmark=px,
                       trial_sharpes=config_sharpes(px, mean_reversion, mr_grid, display_cm),
                       n_folds=5) if len(combined) else None
    result['walk_forward']['mean_reversion'] = {
        'regime': display_key,
        'oos_metrics': metrics_json(compute_metrics(combined)),
        'params_per_fold': [{'lookback': c['lookback'], 'entry_z': c['entry_z']} for c in chosen],
        'oos_equity': {'dates': [d.strftime('%Y-%m-%d') for d in combined.index],
                       'net': series((1 + combined['net']).cumprod(), 6)} if len(combined) else None,
        'diagnostics': json_safe(mr_diag) if mr_diag else None,
    }
    if forecast is not None:
        kgrid = [{'threshold': th} for th in (0.0, 0.001, 0.003, 0.005, 0.01)]
        kfac = lambda p: (lambda prices: kronos_signal(prices, forecast=forecast, **p))
        kcomb, kchosen = walk_forward(px, kfac, kgrid, display_cm, n_folds=5)
        # trial_sharpes=None: kronos_signal needs the cached forecast kwarg that the generic
        # config_sharpes can't supply -- the DSR is still computed, just without the cross-trial
        # variance discount (a small, conservative simplification for this rarely-run path).
        kdiag = diagnose(kcomb, len(kgrid), benchmark=px, n_folds=5) if len(kcomb) else None
        result['walk_forward']['kronos'] = {
            'regime': display_key,
            'oos_metrics': metrics_json(compute_metrics(kcomb)),
            'params_per_fold': [{'threshold': c['threshold']} for c in kchosen],
            'oos_equity': {'dates': [d.strftime('%Y-%m-%d') for d in kcomb.index],
                           'net': series((1 + kcomb['net']).cumprod(), 6)} if len(kcomb) else None,
            'diagnostics': json_safe(kdiag) if kdiag else None,
        }
    return result


def build(spec=None, display_cost=None):
    """Resolve `spec` (None/'synthetic', a CSV path, or a ticker) and build the
    full payload. Convenience wrapper used by the CLI and the API."""
    df, name, source, dq, forecast = resolve_data(spec)
    return build_payload(df, name, source, dq, forecast, display_cost), name


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    result, name = build(path)
    os.makedirs('exports', exist_ok=True)
    out_path = os.path.join('exports', f'{name}.results.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, separators=(',', ':'))
    size_kb = os.path.getsize(out_path) / 1024
    print(f"wrote {out_path}  ({size_kb:.0f} KB, {len(result['strategies'])} strategies, "
          f"{result['meta']['bars']} bars)")


if __name__ == '__main__':
    main()
