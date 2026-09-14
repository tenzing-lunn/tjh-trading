"""Robustness diagnostics (plan/10 Part B) -- so a non-expert can SEE why a result
might be fake, as numbers a beginner can read.

The headline is the **Deflated Sharpe Ratio** (Bailey & Lopez de Prado, 2014): the
probability that an out-of-sample Sharpe reflects genuine skill rather than the luckiest
of N grid-searched configs, corrected for sample length, return skew/kurtosis, and how
many configs were tried. A giant Sharpe found by scanning thousands of variants is mostly
luck; the DSR makes that discount explicit. Rule of thumb: DSR >= 0.95 is significant.

Also here: per-year return + Sharpe (spot the one-year wonder), trades/fold (low count =>
luck), an SPY-tagged regime split (edge only in one regime => fragile), and `red_flags()`
turning all of it into plain English.

Principle (plan/10): the automated flag is a prompt to look closer, NOT a verdict. Flags
guide; the advance/kill call stays human.

Computed from the walk-forward OUTPUT -- it recomputes no backtest math beyond metrics.py.
No scipy: normal CDF via math.erf, inverse-normal via Acklam's algorithm.
"""
import math

import numpy as np
import pandas as pd

from backtest import run_backtest
from metrics import compute_metrics

_EULER = 0.5772156649015329          # Euler-Mascheroni constant, for E[max of N normals]


# ---- normal CDF / inverse CDF (no scipy) -----------------------------------------------
def _norm_cdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p):
    """Inverse standard-normal CDF via Acklam's rational approximation (|err| < 1e-9)."""
    if not 0.0 < p < 1.0:
        return float('-inf') if p <= 0 else float('inf')
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
            ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def _expected_max_z(n):
    """E[max of N iid standard normals] -- how high the best-of-N Sharpe drifts under the
    NULL (no skill). Grows with N: that drift is exactly what we must beat to claim an edge."""
    if n <= 1:
        return 0.0
    return (1 - _EULER) * _norm_ppf(1 - 1.0 / n) + _EULER * _norm_ppf(1 - 1.0 / (n * math.e))


def _moments(x):
    """(skewness, non-excess kurtosis) -- normal has skew 0, kurtosis 3."""
    x = np.asarray(x, float)
    s = x.std(ddof=0)
    if s == 0:
        return 0.0, 3.0
    z = (x - x.mean()) / s
    return float(np.mean(z ** 3)), float(np.mean(z ** 4))


# ---- deflated Sharpe --------------------------------------------------------------------
def deflated_sharpe_ratio(net, n_trials, trial_sharpes=None, ppy=252):
    """P(the OOS Sharpe is real, not the luckiest of `n_trials`). In [0,1]; >=0.95 = significant.

    net           : array of OOS net (per-bar) returns.
    n_trials      : how many configs were searched (grid size) -- the multiple-testing count.
    trial_sharpes : annualized Sharpes of all searched configs (their dispersion sets the bar
                    the best-of-N must clear). If omitted, falls back to the Sharpe estimator's
                    own sampling variance -- less exact, still directional.
    """
    net = np.asarray(net, float)
    net = net[~np.isnan(net)]
    T = len(net)
    sd = net.std(ddof=1) if T > 1 else 0.0
    if T < 20 or sd == 0:
        return float('nan')
    sr = net.mean() / sd                                  # per-observation Sharpe (NOT annual)
    skew, kurt = _moments(net)
    if trial_sharpes is not None and len(np.asarray(trial_sharpes)) > 1:
        ts = np.asarray(trial_sharpes, float) / math.sqrt(ppy)   # de-annualize to per-obs
        var_sr = float(np.nanvar(ts, ddof=1))
    else:
        var_sr = (1 + 0.5 * sr ** 2) / T                  # fallback: estimator sampling variance
    sr0 = math.sqrt(max(var_sr, 0.0)) * _expected_max_z(n_trials)   # threshold Sharpe under null
    denom = math.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr ** 2, 1e-12))
    return float(_norm_cdf((sr - sr0) * math.sqrt(T - 1) / denom))


def config_sharpes(px, fn, grid, cost_model, ppy=252):
    """Full-sample net Sharpe of every config in the grid -- the trial-Sharpe distribution the
    grid search maximizes over (input to the deflated Sharpe). Cheap: one backtest per config."""
    out = []
    for params in grid:
        _, m = run_backtest(px, fn(px, **params), cost_model, ppy)
        out.append(m['sharpe'])
    return out


# ---- benchmark-relative (ACTIVE) deflated Sharpe -----------------------------------------
# `deflated_sharpe_ratio` above asks "did this make money (after paying for N trials)?" -- a
# question pure beta answers YES to (holding SPY scores 0.99). The active versions below ask
# the only question a gate should: "did this beat its BENCHMARK?" Same formula, different input.
def active_returns(strat_df, bench_df):
    """Per-bar ACTIVE return on the shared index: strategy net minus benchmark net.
    Both frames come from run_backtest under the SAME cost model. Rows where either side
    is missing are dropped (never filled)."""
    a = strat_df['net'] - bench_df['net'].reindex(strat_df.index)
    return a.dropna()


def config_active_sharpes(px, fn, grid, cost_model, bench_pos, ppy=252):
    """Annualized ACTIVE Sharpe of every config in the grid -- (config net - benchmark net).
    The trial distribution `active_deflated_sharpe` needs; the active analogue of
    `config_sharpes`. `bench_pos` is the benchmark's position Series (e.g. buy_and_hold(px))."""
    bench, _ = run_backtest(px, bench_pos, cost_model, ppy)
    out = []
    for params in grid:
        o, _ = run_backtest(px, fn(px, **params), cost_model, ppy)
        a = active_returns(o, bench)
        sd = a.std(ddof=1) if len(a) > 1 else 0.0
        out.append(float(a.mean() / sd * math.sqrt(ppy)) if sd > 0 else float('nan'))
    return out


def active_deflated_sharpe(strat_df, bench_df, n_trials, trial_active_sharpes=None, ppy=252):
    """P(the strategy's edge OVER the benchmark is real, not the luckiest of `n_trials`).
    This is the number a gate may consume; `deflated_sharpe_ratio` (vs zero) is display only.

    `trial_active_sharpes` must be ACTIVE Sharpes (see `config_active_sharpes`) or the null
    threshold is in the wrong units. NaN when the active series has no variance -- a strategy
    identical to its benchmark has no edge to test (B&H vs B&H is NaN, not 0.5)."""
    return deflated_sharpe_ratio(active_returns(strat_df, bench_df).values,
                                 n_trials, trial_active_sharpes, ppy)


# ---- consistency: per-year, regime ------------------------------------------------------
def per_year_returns(net_series, ppy=252, bench=None):
    """List of {period, return, sharpe, bars} per calendar year of the OOS net series.

    `bench` (optional): the benchmark's per-bar net return. When given, each row also
    carries `'active'` -- the year's return OVER the benchmark's own return on the same
    bars. That is the series a one-year-wonder check must look at: raw return is mostly
    beta spread across every year, so the flag stays silent even when the whole EDGE is
    one year. Omitted entirely (not None) when `bench` is None, so existing callers see
    exactly the old output."""
    rows = []
    for period, grp in net_series.groupby(net_series.index.to_period('Y')):
        v = grp.values
        sd = v.std(ddof=1) if len(v) > 1 else 0.0
        row = {'period': str(period), 'return': float(np.prod(1 + v) - 1),
               'sharpe': float(v.mean() / sd * math.sqrt(ppy)) if sd > 0 else float('nan'),
               'bars': int(len(v))}
        if bench is not None:
            b = bench.reindex(grp.index).dropna()
            r_b = float(np.prod(1 + b.values) - 1) if len(b) else float('nan')
            row['active'] = ((1 + row['return']) / (1 + r_b) - 1
                             if r_b == r_b and r_b > -1 else float('nan'))
        rows.append(row)
    return rows


def _best_year_share(per_year, key='return'):
    """(best_year, share) where share = the single best year's fraction of the total LOG
    return of `key` ('return' = raw, 'active' = over the benchmark). Log so compounding
    adds up. Returns (None, None) if the total is not positive. A share >= 1 means every
    other year, together, contributed nothing or worse."""
    logs = [(p['period'], math.log(1 + p[key])) for p in per_year
            if p.get(key) == p.get(key) and p.get(key, -2) > -1]
    total = sum(l for _, l in logs)
    if total <= 0 or not logs:
        return None, None
    yr, lg = max(logs, key=lambda t: t[1])
    return yr, lg / total


def regime_split(net_series, benchmark, bench_net=None, lookback=60, band=0.02):
    """Strategy net return in SPY up / down / chop regimes (tagged by trailing SPY trend).

    The tag is `shift(1)`ed: bar t is sorted by the trend that ENDED at t-1, never by a
    window containing its own return.

    `bench_net` (optional): the benchmark's per-bar net return. When given, each regime
    cell also carries `'active'` -- the regime's return over the benchmark's return on the
    same bars. A long-only book "wins in up, loses in down" by construction, so only the
    active cell says anything about the edge."""
    spy = benchmark.reindex(net_series.index).ffill()
    trend = spy.pct_change(lookback).shift(1)
    tag = pd.Series('chop', index=net_series.index)
    tag[trend > band] = 'up'
    tag[trend < -band] = 'down'
    b = bench_net.reindex(net_series.index) if bench_net is not None else None
    out = {}
    for r in ('up', 'down', 'chop'):
        sel = tag == r
        v = net_series[sel].values
        cell = {'return': float(np.prod(1 + v) - 1) if len(v) else 0.0, 'bars': int(len(v))}
        if b is not None:
            bb = b[sel].dropna()
            if len(bb):
                ss = net_series[sel].reindex(bb.index)
                ret_s = float(np.prod(1 + ss.values) - 1)
                ret_b = float(np.prod(1 + bb.values) - 1)
                cell['active'] = (1 + ret_s) / (1 + ret_b) - 1 if ret_b > -1 else float('nan')
            else:
                cell['active'] = float('nan')
        out[r] = cell
    return out


# ---- red flags + orchestrator -----------------------------------------------------------
def red_flags(metrics, diag):
    """Plain-English reasons a result might be fake. Empty list = nothing jumped out
    (still not a green light -- absence of flags is not proof of edge)."""
    out = []
    tpf = diag.get('trades_per_fold')
    if tpf is not None and tpf < 30:
        out.append(f"Only {tpf:.0f} trades/fold -- Sharpe may be luck, not skill.")
    # When a benchmark was supplied upstream the gate consumes the ACTIVE deflated Sharpe,
    # so the prose must quote THAT number -- the raw vs-zero one is display only (pure beta
    # scores 0.99 on it) and would name a statistic no verdict depends on.
    if 'deflated_sharpe_active' in diag:
        dsa = diag['deflated_sharpe_active']
        if dsa is not None and dsa == dsa and dsa < 0.95:
            out.append(f"Edge over the benchmark: active deflated Sharpe {dsa:.2f} "
                       f"(<0.95 => not distinguishable from luck).")
    else:
        dsr, n = diag.get('deflated_sharpe'), diag.get('n_trials')
        if dsr is not None and dsr == dsr and dsr < 0.95:
            out.append(f"Best of {n} configs -- deflated Sharpe {dsr:.2f} (<0.95 => not "
                       f"distinguishable from luck).")
    # One-year wonder. When a benchmark was supplied upstream the per-year rows carry
    # 'active', and the question becomes "was the EDGE one year?" -- the raw version can
    # only see beta, which is spread evenly across years and never trips.
    per_year = diag.get('per_year') or []
    if any('active' in p for p in per_year):
        yr_a, share_a = _best_year_share(per_year, key='active')
        if share_a is not None and share_a > 0.6:
            out.append(f"{share_a*100:.0f}% of the edge over the benchmark came from {yr_a}.")
        if share_a is not None and share_a >= 1.0:
            out.append(f"Edge over the benchmark is fully explained by {yr_a}; "
                       f"the other years net to <= 0.")
    else:
        yr, share = diag.get('best_year'), diag.get('best_year_share')
        if share is not None and share > 0.6:
            out.append(f"{share*100:.0f}% of the return came from {yr} -- a one-year wonder.")
    reg = diag.get('regime_split')
    if reg:
        if any('active' in v for v in reg.values()):
            neg = [k for k, v in reg.items()
                   if v.get('active') == v.get('active') and v['active'] < 0]
            pos = [k for k, v in reg.items()
                   if v.get('active') == v.get('active') and v['active'] > 0]
            if len(neg) >= 2:
                out.append(f"Loses to the benchmark in {', '.join(neg)}; edge is one-regime.")
            elif len(pos) == 1:
                out.append(f"Edge over the benchmark shows only in '{pos[0]}'.")
        else:
            pos = [k for k, v in reg.items() if v['return'] > 0]
            if len(pos) == 1:
                out.append(f"Edge only shows in the '{pos[0]}' regime -- fragile, not robust.")
    return out


def diagnose(oos, n_trials, benchmark=None, trial_sharpes=None, n_folds=5, ppy=252,
             bench_df=None, trial_active_sharpes=None):
    """Full diagnostics dict for one walk-forward OOS result (`oos` = walk_forward's combined
    DataFrame with a 'net' column). Assembles per-year, deflated Sharpe, regime split, and
    the red-flag list. This is what the web app's panel (5) and the verdict log consume.

    `bench_df` (optional): the benchmark's backtest output on the same index, under the same
    cost model (e.g. the ticker's own buy-and-hold walk-forward). When given, the dict also
    carries `deflated_sharpe_active` -- the benchmark-relative number a gate should consume --
    and the per-year / regime cells carry their ACTIVE counterparts, which is what switches
    the one-year-wonder and regime red flags from "did it make money" to "did it beat the
    benchmark". Without it every flag stays on raw return, exactly as before."""
    m = compute_metrics(oos, ppy)
    net = oos['net'].dropna()
    bench_net = bench_df['net'] if bench_df is not None else None
    per_year = per_year_returns(net, ppy, bench=bench_net)
    best_year, share = _best_year_share(per_year)
    diag = {
        'n_trials': n_trials,
        # vs ZERO, beta included -- "did it make money", NOT "did it beat its benchmark".
        'deflated_sharpe': deflated_sharpe_ratio(net.values, n_trials, trial_sharpes, ppy),
        'trades_per_fold': m['num_trades'] / n_folds,
        'per_year': per_year,
        'best_year': best_year,
        'best_year_share': share,
        'regime_split': (regime_split(net, benchmark, bench_net=bench_net)
                         if benchmark is not None else None),
    }
    if bench_df is not None:
        # N = 1, NOT `n_trials`: the walk-forward OOS series carries no grid-selection bias
        # on this axis (params were picked on TRAIN only), so the active edge owes no
        # best-of-N discount here -- scan.py's own gate charges 1 for the same reason. At
        # n=1 the trial-Sharpe dispersion is irrelevant (_expected_max_z(1) == 0), so
        # `trial_active_sharpes` is deliberately not passed through.
        diag['deflated_sharpe_active'] = active_deflated_sharpe(
            oos, bench_df, 1, None, ppy)
    diag['red_flags'] = red_flags(m, diag)
    return diag


if __name__ == '__main__':
    # Self-test: a genuine edge should earn a higher deflated Sharpe than a no-edge fluke,
    # and best-of-many-configs on a random walk must NOT manufacture significance.
    from data import synthetic_ohlcv
    from costs import CostModel
    from strategies import mean_reversion
    from walkforward import walk_forward

    cm = CostModel(3, 1)
    grid = [{'lookback': lb, 'entry_z': z} for lb in (10, 20, 40) for z in (0.5, 1.0, 1.5, 2.0)]
    for name, kappa in [('EDGE  (kappa=0.04)', 0.04), ('NOISE (kappa=0, random walk)', 0.0)]:
        px = synthetic_ohlcv(n=1500, kappa=kappa)['close']
        combined, _ = walk_forward(px, lambda p: (lambda pr: mean_reversion(pr, **p)),
                                   grid, cm, n_folds=5)
        ts = config_sharpes(px, mean_reversion, grid, cm)
        d = diagnose(combined, len(grid), benchmark=px, trial_sharpes=ts)
        print(f"\n{name}: deflated Sharpe = {d['deflated_sharpe']:.3f}  "
              f"(trades/fold {d['trades_per_fold']:.0f}, N={d['n_trials']})")
        for f in d['red_flags']:
            print(f"   flag: {f}")
