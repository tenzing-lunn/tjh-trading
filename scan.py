"""Wide scan -- run the curated strategy library across a whole universe of tickers
and rank the results, HONESTLY.

Philosophy (plan/11): scan wide to DISCOVER candidates, demand a high bar to BELIEVE one.
This file is a thin convenience wrapper over the canonical engine -- it loops
walk_forward() over (ticker x strategy x param-grid) and collects the OUT-OF-SAMPLE,
net-of-costs result for each. It does NOT reimplement costs/backtest/walkforward, and
it introduces no new backtest math.

What it answers: "over a basket of stocks, where (if anywhere) does a strategy's timing
actually beat just holding the index (SPY) out-of-sample, after costs -- and which name is
worth a closer look?" Each ticker is scored independently (no cross-asset coupling), so this
is just a loop; it needs no multi-asset engine.

Honesty rails baked in (rewritten 2026-09-14, audit 2026-09-gates.md 2.5 / plan-12 P0.6):
  * Gate 1 -- every number is net of the LIQUID-ETF cost regime (3/1 bps), not frictionless.
  * Gate 2 -- significance is measured on ACTIVE returns (strategy net MINUS benchmark net),
              never on the raw return. The old gate asked "did this make money?", which pure
              beta in a name that went up 10x answers YES to with zero timing skill: 13 of 93
              rows passed it on beta alone. Now every row must clear a deflated Sharpe against
              BOTH its own ticker's buy&hold AND holding SPY, over the identical OOS dates.
  * Gate 3 -- the multiple-testing discount is charged on the N that is actually searched by a
              HUMAN: the len(rows) results of this scan. (The grid N is still printed in the N
              column to document the search -- but the walk-forward OOS series has no in-sample
              selection bias on the grid axis, so charging it there was a category error.)
  * Gate 4 -- trades/fold is shown and flagged when < 30 (too few trades = luck, not edge), and
              the random bar is a PERCENTILE over N_RANDOM holding-period-matched coin flips,
              not one seed of a bar-by-bar coin flip that bleeds costs and loses to everything.

    python scan.py                       # scan every realdata/*.csv
    python scan.py realdata/tqqq.csv f.csv  # scan a chosen subset
"""
import glob
import os
import sys
import time

import numpy as np
import pandas as pd

from data import load_csv
from costs import CostModel
from metrics import compute_metrics, active_metrics
from strategies import buy_and_hold, sma_crossover, mean_reversion, time_series_momentum
from walkforward import walk_forward
from diagnostics import (diagnose, config_sharpes, active_returns, active_deflated_sharpe,
                         deflated_sharpe_ratio)
from verdict_log import append_verdict, scan_row_to_record

# The truth-for-equities regime. Frictionless is a lie; options are a separate study.
ETF_COST = CostModel(spread_bps=3, slippage_bps=1)
N_FOLDS = 5
MIN_TRADES_PER_FOLD = 30           # Gate-4 flag: fewer than this per fold => suspect
DSR_BAR = 0.95                     # deflated Sharpe >= this = "not distinguishable from luck" cleared
N_RANDOM = 200                     # seeds in the holding-period-matched random baseline
RAND_BAR = 0.95                    # candidate must beat this fraction of the random draws

# Candidate signals we actually scan (economically distinct families only, per plan/11).
CANDIDATES = {
    'sma':     (sma_crossover,
                [{'fast': f, 'slow': s} for f in (10, 20, 50) for s in (100, 150, 200)]),
    'meanrev': (mean_reversion,
                [{'lookback': lb, 'entry_z': z}
                 for lb in (10, 20, 40) for z in (0.5, 1.0, 1.5, 2.0)]),
    # First REASONED strategy (Thesis 001 family): trend persistence has a documented
    # economic story. Small grid on purpose -- 12-1 is the canonical spec, not a search.
    'tsmom':   (time_series_momentum,
                [{'lookback': lb, 'skip': 21} for lb in (126, 252)]),
}
# The two benchmarks every candidate is measured AGAINST (not merely compared to): the
# ticker's own buy&hold and holding SPY, both run through the SAME folds and cost model.
# There is no single-seed random baseline any more -- see _random_percentile.


def _factory(fn):
    """Adapt a signal fn to walk_forward's strat_factory(params) -> (prices -> positions)."""
    return lambda params: (lambda prices: fn(prices, **params))


def _oos(px, fn, grid, cost_model=ETF_COST, n_folds=N_FOLDS):
    """Walk-forward one (signal, grid) on a price series; return (OOS metrics, OOS frame).
    The OOS index is identical across strategies on a ticker (folds depend only on length),
    so callers reuse the buy&hold run's frame as both the ticker's OOS window and the
    benchmark the candidate's ACTIVE return is measured against."""
    combined, _ = walk_forward(px, _factory(fn), grid, cost_model, n_folds=n_folds)
    m = compute_metrics(combined)
    m['n_trials'] = len(grid)
    return m, combined


def _ge(v, bar):
    """NaN-safe 'clears the bar'. A NaN statistic never clears a gate: an active series with
    no variance (a strategy indistinguishable from its benchmark) has no edge to test."""
    return v == v and v >= bar


def _random_holding(prices, k=1, seed=0, p_long=0.5, **kw):
    """Long/flat coin flip REDRAWN EVERY k BARS -- the holding-period-matched random null
    (audit 2.4). strategies.random_strategy redraws every bar, so it turns over ~50% daily,
    bleeds ~2.5 bps a day and loses to everything: "beats random" was a bar nothing could
    fail. Matching k to the candidate's own average holding period makes the coin flip pay
    roughly the SAME costs, so what's compared is timing skill, not turnover.
    Scan-specific baseline construction, deliberately not a general-purpose signal."""
    k = max(int(k), 1)
    n = len(prices)
    draws = np.random.default_rng(seed).random((n + k - 1) // k) < p_long
    return pd.Series(np.repeat(draws.astype(float), k)[:n], index=prices.index)


def _random_percentile(px, active_ret, num_trades, bh_comb, cost_model, n_folds,
                       n_random=N_RANDOM):
    """(percentile, median random OOS return) for the candidate against `n_random`
    holding-period-matched coin flips run through the SAME folds and cost model.
    The percentile is over ACTIVE return vs the ticker's own buy&hold -- so it answers
    "how many equally-lazy random schedules would have beaten the stock by more?".
    A real bar: rand_pct 0.95 means the candidate beat 95% of them."""
    k = len(bh_comb) / num_trades if num_trades else len(bh_comb)
    beaten, totals = 0, []
    ok = active_ret == active_ret
    for seed in range(n_random):
        m, comb = _oos(px, _random_holding, [{'k': k, 'seed': seed}], cost_model, n_folds)
        totals.append(m['total_return'])
        ra = active_metrics(comb, bh_comb)['active_return']
        beaten += bool(ok and ra == ra and active_ret > ra)
    return beaten / n_random, float(np.median(totals))


def _binding_dsr(r):
    """The one DSR to show in the table: the gate that BINDS (the weakest of the three).
    NaN if any leg is NaN -- an untestable leg is a failed leg, never a passing average."""
    vals = (r['dsr_vs_bh'], r['dsr_vs_spy'], r['dsr_scan'])
    return float('nan') if any(v != v for v in vals) else float(min(vals))


def scan_universe(paths, benchmark=None, cost_model=ETF_COST, n_folds=N_FOLDS):
    """Loop the curated library over a universe. Returns a list of result dicts, one per
    (ticker, candidate strategy), each carrying its OOS-net-of-costs metrics AND the
    significance of its edge over the two benchmarks it is measured against: the ticker's
    own buy&hold and (if a `benchmark` close Series -- SPY -- is given) holding the index,
    both run through the identical folds and cost model.

    The verdict is a statement about ACTIVE return (strategy net MINUS benchmark net), never
    about raw return: "it made money" is a question pure beta answers yes to."""
    rows, actives = [], []                      # actives[i] = row i's per-bar active-vs-B&H
    for path in paths:
        ticker = os.path.splitext(os.path.basename(path))[0]
        px = load_csv(path)['close']

        # ---- per ticker, computed ONCE: the benchmarks, through the SAME folds ----------
        bh_m, bh_comb = _oos(px, buy_and_hold, [{}], cost_model, n_folds)
        bh, oos_idx = bh_m['total_return'], bh_comb.index
        spy_comb, spy = None, None
        if benchmark is not None:
            # SPY re-dated onto the ticker's calendar so the folds (and so the OOS window)
            # are identical. ffill only -- never backfill, that would invent pre-history.
            _, spy_comb = _oos(benchmark.reindex(px.index).ffill(), buy_and_hold, [{}],
                               cost_model, n_folds)
            b = benchmark.reindex(oos_idx).dropna()
            if len(b) > 1:                      # display: hold-SPY return over the OOS window
                spy = float(b.iloc[-1] / b.iloc[0] - 1)

        for strat, (fn, grid) in CANDIDATES.items():
            m, combined = _oos(px, fn, grid, cost_model, n_folds)
            # diagnose() stays purely explanatory (the printed red-flag prose); it gates
            # nothing. Its raw 'deflated_sharpe' is the vs-ZERO number, display only.
            diag = diagnose(combined, len(grid), benchmark=benchmark,
                            trial_sharpes=config_sharpes(px, fn, grid, cost_model),
                            n_folds=n_folds, bench_df=bh_comb)
            am = active_metrics(combined, bh_comb)
            # Gate 2 -- significance of the edge OVER each benchmark. n_trials=1 because the
            # walk-forward OOS series carries no in-sample selection on the grid axis (params
            # were picked on train only); the honest best-of-N charge is levied once, at scan
            # level, in the second pass below.
            dsr_vs_bh = active_deflated_sharpe(combined, bh_comb, n_trials=1)
            dsr_vs_spy = (active_deflated_sharpe(combined, spy_comb, n_trials=1)
                          if spy_comb is not None else 1.0)   # no SPY on disk => don't block
            ret, tpf = m['total_return'], m['num_trades'] / n_folds
            rand_pct, rand_ret = _random_percentile(px, am['active_return'], m['num_trades'],
                                                    bh_comb, cost_model, n_folds)
            rows.append({
                'ticker': ticker, 'strategy': strat, 'metrics': m,
                'bh_return': bh, 'rand_return': rand_ret, 'spy_return': spy,
                # display-only comparisons (point estimates, no error bar -- never gates)
                'beats_bh': ret > bh, 'beats_spy': spy is None or ret > spy,
                'beats_rand': rand_pct >= RAND_BAR,
                # the gates
                'dsr_vs_bh': dsr_vs_bh, 'dsr_vs_spy': dsr_vs_spy, 'rand_pct': rand_pct,
                'active_return_vs_bh': am['active_return'],
                'active_sharpe_vs_bh': am['information_ratio'],
                'raw_dsr_vs_zero': diag['deflated_sharpe'],
                'red_flags': diag['red_flags'],
                'trades_per_fold': tpf, 'thin': tpf < MIN_TRADES_PER_FOLD,
            })
            actives.append(active_returns(combined, bh_comb).values)

    # ---- Gate 3, levied ONCE, on the N a HUMAN actually searches ------------------------
    # The selection that really happens is reading the best of these len(rows) OOS results.
    # (The grid N stays in the printed N column to document the search; charging it there
    #  would be a category error -- walk-forward already removed that selection bias.)
    trial_act = [r['active_sharpe_vs_bh'] for r in rows]
    for r, a in zip(rows, actives):
        r['dsr_scan'] = deflated_sharpe_ratio(a, n_trials=len(rows), trial_sharpes=trial_act)
        r['dsr'] = _binding_dsr(r)              # the gate that binds (also the legacy key)
        r['significant'] = (_ge(r['dsr_vs_bh'], DSR_BAR) and _ge(r['dsr_vs_spy'], DSR_BAR)
                            and _ge(r['dsr_scan'], DSR_BAR))
        # Legacy key (engine_api / export_track_record / the webapp read it): now "worth a
        # second look" = significant on at least one benchmark leg, i.e. _verdict's 'suspect'.
        r['survives_gate2'] = _ge(r['dsr_vs_bh'], DSR_BAR) or _ge(r['dsr_vs_spy'], DSR_BAR)
        r['clean'] = (r['significant'] and r['metrics']['total_return'] > 0
                      and r['trades_per_fold'] >= MIN_TRADES_PER_FOLD
                      and r['rand_pct'] >= RAND_BAR)
    return rows


def _pct(v, width=7):
    if v is None or v != v:
        return format('nan', f'>{width}') + ' '
    return format(v * 100, f'{width}.1f') + '%'


def _verdict(r):
    # 'EDGE?' = the edge over BOTH benchmarks survived the discount, and it is positive,
    # non-thin and better than 95% of holding-period-matched coin flips.
    # 'suspect' = significant against one benchmark leg only -- a prompt to look, not a pass.
    return ('EDGE?' if r['clean'] else
            'suspect' if r['survives_gate2'] else 'dead')


HDR = ("  ticker strat     N   OOS ret   Sharpe   maxDD   trds  t/fold    vsSPY "
       "minDSR  rand%  verdict")


def _dsr(v):
    return f"{v:5.2f}" if v is not None and v == v else "  nan"


def _line(r):
    m = r['metrics']
    flag = ' *thin' if r['thin'] else ''
    vs = _pct(m['total_return'] - r['spy_return'], 7) if r['spy_return'] is not None else '   n/a '
    return (f"  {r['ticker']:6s} {r['strategy']:7s} {m['n_trials']:3d} "
            f"{_pct(m['total_return'])}  {m['sharpe']:6.2f}  {_pct(m['max_drawdown'], 6)} "
            f"{m['num_trades']:5d} {r['trades_per_fold']:6.1f} {vs} {_dsr(r['dsr'])}  "
            f"{r['rand_pct'] * 100:4.0f}%  {_verdict(r)}{flag}")


def main():
    args = sys.argv[1:]
    log = '--log' in args                       # opt-in: record the meaningful rows as verdicts
    args = [a for a in args if a != '--log']
    paths = args or sorted(glob.glob('realdata/*.csv'))
    if not paths:
        print("No CSVs to scan. Pass paths or run fetch_universe.py into realdata/.")
        return
    # SPY is the opportunity-cost benchmark ("would I have been better off in the index?").
    benchmark = None
    if os.path.exists('realdata/spy.csv'):
        benchmark = load_csv('realdata/spy.csv', warn=False)['close']

    t0 = time.time()
    rows = scan_universe(paths, benchmark=benchmark)
    elapsed = time.time() - t0

    tickers = sorted({r['ticker'] for r in rows})
    rows.sort(key=lambda r: (r['metrics']['total_return']
                             if r['metrics']['total_return'] == r['metrics']['total_return']
                             else -1e9), reverse=True)

    print(f"\nWIDE SCAN -- {len(tickers)} tickers x {len(CANDIDATES)} strategies "
          f"= {len(rows)} backtests, walk-forward OOS, net of LIQUID-ETF costs (3/1 bps), "
          f"{N_FOLDS} folds")
    bench = ("judged vs HOLDING SPY over the same window" if benchmark is not None
             else "(no realdata/spy.csv -> vsSPY blank)")
    print(f"{bench}.  Ran in {elapsed:.2f}s "
          f"({elapsed / max(len(rows), 1) * 1000:.0f} ms/backtest) -- compute is a non-issue.\n")

    edges = [r for r in rows if r['clean']]
    suspects = [r for r in rows if r['survives_gate2'] and not r['clean']]
    print(f"RESULT: {len(edges)} EDGE?  |  {len(suspects)} suspect  |  "
          f"{len(rows) - len(edges) - len(suspects)} dead   (of {len(rows)})\n")

    # Record the rows that warrant a human look (edges + gate-2 survivors) into the
    # verdict log. The 80-odd dead backtests are the expected base rate, not a track record;
    # logging them all would bury the meaningful rows and stack on every re-run.
    if log:
        for r in edges + suspects:
            append_verdict(scan_row_to_record(r))
        print(f"Logged {len(edges) + len(suspects)} verdict record(s) to verdicts.jsonl "
              f"({len(edges)} EDGE? + {len(suspects)} suspect).\n")

    if edges:
        print("EDGE? candidates (active DSR >=0.95 vs B&H, vs SPY and after the scan-wide "
              "discount; positive; >=30 trades/fold; beats >=95% of matched coin flips):")
        print(HDR); print("  " + "-" * 95)
        for r in edges:
            print(_line(r))
        print()

    top_n = min(20, len(rows))
    print(f"TOP {top_n} by OOS net return (context -- most of these are noise):")
    print(HDR); print("  " + "-" * 95)
    for r in rows[:top_n]:
        print(_line(r))

    # The machine explaining ITSELF: why the biggest-looking numbers are not edges.
    print("\nWhy the top 5 numbers are not edges (auto red flags -- a prompt to look, not a verdict):")
    for r in rows[:5]:
        flags = r['red_flags'] or ['(no automated flag -- but costs + N-trial discount still apply)']
        print(f"  {r['ticker'].upper()}/{r['strategy']}  ({_pct(r['metrics']['total_return']).strip()}):")
        for f in flags:
            print(f"     - {f}")

    print("\n" + "-" * 90)
    if edges:
        top = edges[0]
        print(f"Closest look -> {top['ticker'].upper()} / {top['strategy']}: "
              f"OOS {_pct(top['metrics']['total_return'])} net, active {_pct(top['active_return_vs_bh'])} "
              f"over its own buy&hold, {top['trades_per_fold']:.0f} trades/fold, "
              f"active DSR {top['dsr_vs_bh']:.2f} vs B&H / {top['dsr_vs_spy']:.2f} vs SPY / "
              f"{top['dsr_scan']:.2f} after the {len(rows)}-row scan discount, "
              f"beating {top['rand_pct'] * 100:.0f}% of matched coin flips.")
        print("  It cleared Gates 1-3 (costs, OOS active-vs-benchmark, multiple-testing). Before")
        print("  it is believed it STILL needs Gate 4: Jonathan's thesis for WHY the edge exists")
        print("  and who is on the other side. A green number with no economic story is luck.")
    else:
        print(f"No clean survivor in {len(rows)} backtests across {len(tickers)} liquid names.")
        print("No strategy's edge OVER its benchmark -- its own buy&hold AND holding SPY, same")
        print("folds, same costs -- is distinguishable from luck, once the best-of-N discount")
        print(f"for the {len(rows)} results a human reads in this table is charged.")
        print("That is the honest base rate: on liquid daily bars, simple timing rules do not")
        print("beat just holding the index. The scan did its job by refusing a fake winner.")
    print("* thin = fewer than 30 trades/fold; treat its Sharpe as noise.")
    print(f"minDSR = the binding leg of (vs B&H, vs SPY, scan-wide); rand% = percentile vs "
          f"{N_RANDOM} holding-period-matched coin flips.\n")


if __name__ == '__main__':
    main()
