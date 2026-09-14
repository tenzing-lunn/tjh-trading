---
tags: [algo-trading, backtest]
source: run.py
---
# Run — Entry Point

Wires everything together: runs the baselines + a candidate strategy under several
[[Costs|cost regimes]], then a [[Walkforward|walk-forward]] (out-of-sample) test, and
prints the comparison table. Auto-adds a `kronos` row + its own OOS walk-forward if a
`<ticker>.kronos.csv` sidecar exists next to the price CSV (from `forecast_kronos.py`).
Every real walk-forward (non-synthetic) also auto-appends a machine-readable verdict row
to `verdicts.jsonl` via `verdict_log.py` (plan/10 Part A) — nothing here retypes a result.

## Usage
```bash
python3 run.py            # synthetic data (always works)
python3 run.py spy.csv    # real data, fetched locally via fetch_data.py
python3 run.py realdata/tqqq.csv   # 'kronos' row appears automatically if tqqq.kronos.csv exists
```

With no argument it uses the [[Data|synthetic]] fixture with a mild edge baked in
(`kappa=0.04`) so you can watch the full pipeline. Real markets are much closer to
`kappa=0` (no edge).

## What it prints
For each of the three regimes — FRICTIONLESS, LIQUID ETF, CHEAP OPTION — it scores
[[Strategies|strategies]]: `buy_and_hold`, `random`, `sma_20_100`, `meanrev_20_1`, and
`kronos` (only if a forecast sidecar is present). Then a walk-forward row where
mean-reversion parameters are chosen **out-of-sample** (plus a second walk-forward row
for `kronos` if it ran), each followed by a `diagnostics.py` verdict-log line.

> [!tip] Reading the output
> - **FRICTIONLESS** = the lie. Raw signal only.
> - **LIQUID ETF** = the truth for stocks.
> - **CHEAP OPTION** = why frequent options trading → ~−100%.
> - **OOS combined** = the only row that isn't lying to you.

## Code
```python
import os
import sys
from functools import partial
import pandas as pd
from data import synthetic_ohlcv, load_csv
from costs import CostModel
from backtest import run_backtest
from metrics import compute_metrics
from strategies import (buy_and_hold, random_strategy, sma_crossover,
                        mean_reversion, kronos_signal)
from walkforward import walk_forward
from diagnostics import diagnose, config_sharpes
from verdict_log import append_verdict


def load_kronos_forecast(path):
    """If a forecast_kronos.py sidecar (<stem>.kronos.csv) exists next to the price
    CSV, load its pred_ret column. Returns None if absent (Kronos rows are skipped)."""
    if not path:
        return None
    sidecar = path.rsplit(".", 1)[0] + ".kronos.csv"
    if not os.path.exists(sidecar):
        return None
    fc = pd.read_csv(sidecar, parse_dates=[0], index_col=0)["pred_ret"]
    return fc


def log_wf_verdict(strategy, px, combined, chosen, grid, trial_sharpes, m, path):
    """Append one machine-readable verdict row (plan/10 Part A). Records only what the
    engine already computed; the judgment column stays human (Tenzing's)."""
    if len(combined) == 0:
        return
    lo, hi = combined.index[0], combined.index[-1]
    win = px.loc[lo:hi]
    bh = float(win.iloc[-1] / win.iloc[0] - 1)
    spy_ret, bench = None, px
    if os.path.exists('realdata/spy.csv'):
        spy = load_csv('realdata/spy.csv')['close']
        s = spy.loc[lo:hi]
        if len(s) > 1:
            spy_ret, bench = float(s.iloc[-1] / s.iloc[0] - 1), spy
    d = diagnose(combined, len(grid), benchmark=bench, trial_sharpes=trial_sharpes)
    append_verdict({
        'ticker': os.path.splitext(os.path.basename(path))[0] if path else 'synthetic',
        'strategy': strategy, 'params': chosen,
        'cost_regime': '3/1 bps (liquid ETF)',
        'oos_total_return': m['total_return'], 'oos_sharpe': m['sharpe'],
        'oos_max_dd': m['max_drawdown'], 'num_trades': m['num_trades'],
        'buy_hold_return': bh, 'spy_return': spy_ret,
        'beats_bh': bool(m['total_return'] > bh),
        'deflated_sharpe': d['deflated_sharpe'], 'trades_per_fold': d['trades_per_fold'],
        'per_year': d['per_year'], 'regime_split': d['regime_split'],
        'red_flags': d['red_flags'],
        'synthetic': path is None,
    })


def fmt(m):
    f = lambda v, s='6.1f': (format(v * 100, s) if v == v else ' nan')
    return (f"ret={f(m['total_return'])}%  Sharpe={m['sharpe']:5.2f}  "
            f"maxDD={f(m['max_drawdown'])}%  trades={m['num_trades']:4d}  "
            f"win={f(m['win_rate'],'4.1f')}%")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path:
        df = load_csv(path); src = f"REAL data: {path}"
    else:
        # mild edge baked in so we see the full pipeline; real markets are much closer to kappa=0
        df = synthetic_ohlcv(n=1500, kappa=0.04)
        src = "SYNTHETIC (kappa=0.04 edge baked in). Sandbox has no internet; use fetch_data.py for SPY/QQQ."
    px = df['close']
    print(f"Data: {src}\nbars={len(px)}\n")

    forecast = load_kronos_forecast(path)

    regimes = [
        ('FRICTIONLESS (the lie)',     CostModel(spread_bps=0,   slippage_bps=0)),
        ('LIQUID ETF (SPY-like)',      CostModel(spread_bps=3,   slippage_bps=1)),
        ('CHEAP OPTION spread',        CostModel(spread_bps=300, slippage_bps=50)),
    ]
    strats = {
        'buy_and_hold': (buy_and_hold, {}),
        'random':       (random_strategy, {'seed': 1}),
        'sma_20_100':   (sma_crossover, {'fast': 20, 'slow': 100}),
        'meanrev_20_1': (mean_reversion, {'lookback': 20, 'entry_z': 1.0}),
    }
    if forecast is not None:
        strats['kronos'] = (kronos_signal, {'forecast': forecast, 'threshold': 0.0})
    for label, cm in regimes:
        print(f"=== {label} ===")
        for name, (fn, kw) in strats.items():
            _, m = run_backtest(px, fn(px, **kw), cm)
            print(f"  {name:14s} {fmt(m)}")
        print()

    print("=== WALK-FORWARD: mean reversion, params chosen OUT-OF-SAMPLE, ETF costs ===")
    grid = [{'lookback': lb, 'entry_z': z}
            for lb in (10, 20, 40) for z in (0.5, 1.0, 1.5, 2.0)]
    factory = lambda p: (lambda prices: mean_reversion(prices, **p))
    combined, chosen = walk_forward(px, factory, grid, CostModel(3, 1), n_folds=5)
    m = compute_metrics(combined)
    print(f"  OOS combined   {fmt(m)}")
    print(f"  params/fold:   {[ (c['lookback'], c['entry_z']) for c in chosen ]}")
    log_wf_verdict('meanrev_wf', px, combined, chosen, grid,
                   config_sharpes(px, mean_reversion, grid, CostModel(3, 1)), m, path)

    if forecast is not None:
        print("\n=== WALK-FORWARD: KRONOS, threshold chosen OUT-OF-SAMPLE, ETF costs ===")
        kgrid = [{'threshold': th} for th in (0.0, 0.001, 0.003, 0.005, 0.01)]
        kfactory = lambda p: (lambda prices: kronos_signal(prices, forecast=forecast, **p))
        kcomb, kchosen = walk_forward(px, kfactory, kgrid, CostModel(3, 1), n_folds=5)
        km = compute_metrics(kcomb)
        print(f"  OOS combined   {fmt(km)}")
        print(f"  thresh/fold:   {[c['threshold'] for c in kchosen]}")
        log_wf_verdict('kronos_wf', px, kcomb, kchosen, kgrid,
                       config_sharpes(px, partial(kronos_signal, forecast=forecast),
                                      kgrid, CostModel(3, 1)), km, path)

    print("\n(OOS = out-of-sample: the only row that isn't lying to you.)")


if __name__ == '__main__':
    main()
```

## See also
- [[Data]] — synthetic fixture + CSV loader feeding `px`
- [[Costs]] — the three regimes
- [[Strategies]] — the candidates scored
- [[Backtest]] / [[Metrics]] — engine + scoring
- [[Walkforward]] — the out-of-sample row
