"""Cross-sectional momentum panel backtest -- Thesis 001.

The single-name engine (backtest.py) scores one ticker at a time; cross-sectional
momentum needs the whole panel at once: each month, rank every stock by its 12-1
trailing return (12 months back, skipping the most recent month) and hold the top
names equal-weight. Economic story: intermediate-horizon winners keep winning
(Jegadeesh-Titman 1993) via investor underreaction / slow information diffusion.

Honesty rails (same skeptic's bar as scan.py):
  * No lookahead: weights decided at month-end t are HELD from t+1 (weights.shift(1)),
    identical to the engine convention.
  * Net of the LIQUID-ETF cost regime (3/1 bps) on FULL portfolio turnover.
  * Canonical spec only (12-1, monthly, top 10, long-only). n_trials=1 -- we do not
    grid-search the thesis; a searched thesis is a different (weaker) claim.
  * Three baselines through the SAME dates and costs:
      - SPY buy&hold (the opportunity-cost bar),
      - equal-weight ALL eligible stocks (was it selection skill, or just the universe?),
      - random top-N picks each month (would any 10 names have worked?).
  * LOUD survivorship caveat: the universe is today's liquid names, so every ticker
    "survived" by construction. That inflates all long-only results here, including
    the baselines -- which is exactly why beating the EW-universe is the bar that
    matters most, not beating SPY.

    python3 xsect.py                # run Thesis 001 on realdata/
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

from costs import CostModel
from data import load_csv
from metrics import compute_metrics
from diagnostics import deflated_sharpe_ratio, regime_split, effective_n_trials
from verdict_log import append_verdict
import power
import ledger

# The experiment-ledger research question this panel belongs to (plan/14 I1.6).
LEDGER_FAMILY = "thesis-001-xsect"

ETF_COST = CostModel(spread_bps=3, slippage_bps=1)
# The benchmark and pure index/leveraged products are not cross-sectional candidates.
EXCLUDE = {'spy', 'qqq', 'dia', 'iwm', 'vti', 'tqqq'}
TOP_N = 10
LOOKBACK, SKIP = 252, 21       # canonical 12-1 in daily bars
# Robustness-sweep neighborhood (SENSITIVITY only -- NOT a grid search; see sweep()).
SWEEP_LOOKBACKS = {'6mo': 126, '9mo': 189, '12mo': 252}
SWEEP_TOP_NS = [5, 10, 15]


def load_panel(paths):
    """Outer-join the close series of every CSV into one (dates x tickers) panel."""
    closes = {}
    for p in paths:
        t = os.path.splitext(os.path.basename(p))[0]
        closes[t] = load_csv(p, warn=False)['close']
    return pd.DataFrame(closes).sort_index()


def momentum_12_1(panel, lookback=LOOKBACK, skip=SKIP):
    """Score[t, name] = return from t-lookback to t-skip. NaN until enough history."""
    past = panel.shift(skip)
    return past / past.shift(lookback - skip) - 1.0


def month_end_mask(index):
    """True on the last trading day of each calendar month in the index."""
    s = pd.Series(1, index=index)
    last = s.groupby([index.year, index.month]).tail(1).index
    return index.isin(last)


def _eligible_at(row, eligible, t):
    """Point-in-time universe filter. `eligible` is a boolean (dates x tickers) frame:
    a name is selectable at month-end t only if eligible.loc[t, name] is True. Used by the
    point-in-time S&P 500 panel (pit_panel.py) so a backtest can only pick names that were
    ACTUALLY in the index on that date. When eligible is None this is never called and the
    default behaviour is untouched."""
    if t not in eligible.index:
        return row.iloc[:0]
    mask = eligible.loc[t].reindex(row.index).fillna(False).astype(bool)
    return row[mask]


def target_weights(panel, top_n=TOP_N, lookback=LOOKBACK, picker=None, eligible=None):
    """Daily target-weight DataFrame: at each month-end, long the top_n names by 12-1
    momentum (equal weight), hold until the next rebalance. `picker` overrides the
    selection (used by the random baseline); it gets (scores_row) -> list of names.
    `lookback` is exposed only for the robustness sweep -- the canonical spec uses the default.
    `eligible` (optional, default None = every existing caller) restricts what is selectable
    at each rebalance to a point-in-time universe; see _eligible_at."""
    scores = momentum_12_1(panel, lookback=lookback)
    rebal = month_end_mask(panel.index)
    w = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for t in panel.index[rebal]:
        row = scores.loc[t].dropna()
        if eligible is not None:
            row = _eligible_at(row, eligible, t)
        if len(row) < top_n:            # not enough names with a full year of history yet
            continue
        names = picker(row) if picker else row.nlargest(top_n).index
        wt = pd.Series(0.0, index=panel.columns)
        wt[list(names)] = 1.0 / top_n
        w.loc[t] = wt
    return w.ffill().fillna(0.0)


def run_panel(panel, weights, cost_model=ETF_COST):
    """Panel analog of run_backtest: same shift(1) no-lookahead, same cost math,
    output shaped so compute_metrics works unchanged."""
    rets = panel.pct_change(fill_method=None).fillna(0.0)
    held = weights.shift(1).fillna(0.0)
    turnover = (weights - weights.shift(1)).abs().sum(axis=1).fillna(0.0)
    gross = (held * rets).sum(axis=1)
    cost = pd.Series(cost_model.cost_fraction(turnover.values), index=panel.index)
    net = gross - cost
    out = pd.DataFrame({'ret': gross, 'turnover': turnover, 'gross': gross,
                        'cost': cost, 'net': net, 'held': held.abs().sum(axis=1)})
    out['equity'] = (1 + net).cumprod()
    return out


def _first_active(df):
    """Trim the warm-up (weights all zero) so metrics reflect only the live period."""
    live = df.index[df['held'] > 0]
    return df.loc[live[0]:] if len(live) else df


def _pct(v):
    return f"{v * 100:8.1f}%" if v == v else '     nan'


def _ew_weights(panel, lookback, eligible=None):
    """Equal-weight ALL names that have a valid momentum score at each month-end -- the
    'just own the universe' baseline for a given lookback (eligibility tracks the lookback).
    `eligible` (optional, default None) narrows 'the universe' to the point-in-time members."""
    scores = momentum_12_1(panel, lookback=lookback)
    rebal = month_end_mask(panel.index)
    w = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for t in panel.index[rebal]:
        row = scores.loc[t].dropna()
        if eligible is not None:
            row = _eligible_at(row, eligible, t)
        if len(row) < 1:
            continue
        wt = pd.Series(0.0, index=panel.columns)
        wt[row.index] = 1.0 / len(row)
        w.loc[t] = wt
    return w.ffill().fillna(0.0)


def robustness(res, spy_close, ew_res=None, family=LEDGER_FAMILY):
    """The scan's gauntlet applied to one panel result -> {psr, months, regimes, flags}.
    Shared by the CLI and the track-record export so both tell the SAME story. Probabilistic
    Sharpe is scored on MONTHLY returns (a monthly strategy: daily bars would count ~21
    held-flat days as 21 independent wins and overstate significance).

    `ew_res` (the EW-universe panel result) is what makes the gauntlet honest. Without it
    every number here is measured against ZERO, and owning a rising basket passes: momentum,
    the EW universe and five seeds of RANDOM top-10 picks all score PSR ~1.00 (audit 4.1).
    With it, `psr` becomes the ACTIVE PSR -- P(the edge over the EW-universe is > 0) -- and
    the one-year / regime flags read the active series too. `psr` is deliberately an ALIAS
    for the honest number so every existing consumer gets it without changing; `psr_raw` and
    `psr_active` are also returned for anyone who wants to see both.

    `family`: experiment-ledger research question (see ledger.py). Defaults to Thesis 001's
    family so the CLI, the live Engine Room and the export all charge the SAME N to the
    active PSR. Only the active (gate) number is ledger-informed; `psr_raw` is reference-only
    and stays P(Sharpe > 0)."""
    monthly = _monthly_returns(res['net'])
    psr_raw = deflated_sharpe_ratio(monthly.values, n_trials=1, ppy=12)  # n=1 => P(Sharpe > 0)
    psr_active = float('nan')
    bench_net = None
    if ew_res is not None:
        bench_net = ew_res['net']
        active = (monthly - _monthly_returns(bench_net)).dropna()
        psr_active = deflated_sharpe_ratio(active.values, n_trials=1, ppy=12, family=family)
    psr = psr_active if ew_res is not None else psr_raw
    regimes = (regime_split(res['net'], spy_close, bench_net=bench_net)
               if spy_close is not None else None)
    flags = []
    if psr == psr and psr < 0.95:
        n_used = effective_n_trials(1, family)
        n_note = f" (N={n_used}, ledger-informed)" if n_used > 1 else ""
        flags.append(f"Probabilistic Sharpe {psr:.2f}{n_note} < 0.95 -- not clearly distinguishable "
                     "from " + ("the EW-universe." if ew_res is not None else "zero."))
    # The EDGE by year, not the return by year: raw return is mostly beta, spread across
    # every year, so a one-year edge hides behind it (audit 3.1).
    yearly = []
    for y, g in res.groupby(res.index.year):
        r = (1 + g['net']).prod() - 1
        if bench_net is not None:
            b = bench_net.reindex(g.index).dropna()
            r_b = (1 + b).prod() - 1 if len(b) else float('nan')
            r = (1 + r) / (1 + r_b) - 1 if r_b == r_b and r_b > -1 else float('nan')
        yearly.append((y, float(r)))
    ylogs = [(y, np.log(1 + r)) for y, r in yearly if r == r and r > -1]
    ytot = sum(l for _, l in ylogs)
    what = 'edge over the EW-universe' if ew_res is not None else '(log) return'
    if ytot > 0 and ylogs:
        by, bl = max(ylogs, key=lambda t: t[1])
        if bl / ytot > 0.6:
            flags.append(f"{bl/ytot*100:.0f}% of the {what} came from {by} -- a one-year wonder.")
        if bl / ytot >= 1.0:
            flags.append(f"The {what} is fully explained by {by}; the other years net to <= 0.")
    if regimes:
        if ew_res is not None:
            neg = [r for r in ('up', 'down', 'chop')
                   if regimes[r].get('active') == regimes[r].get('active')
                   and regimes[r]['active'] < 0]
            pos = [r for r in ('up', 'down', 'chop')
                   if regimes[r].get('active') == regimes[r].get('active')
                   and regimes[r]['active'] > 0]
            if len(neg) >= 2:
                flags.append(f"Loses to the EW-universe in {', '.join(neg)} regimes "
                             f"-- the edge is one-regime, not all-weather.")
            elif len(pos) == 1:
                flags.append(f"Edge over the EW-universe shows only in the '{pos[0]}' regime.")
        else:
            worst = min(('up', 'down', 'chop'), key=lambda r: regimes[r]['return'])
            if regimes[worst]['return'] < -0.05:     # materially loses money in some regime
                flags.append(f"Loses in the '{worst}' regime ({_pct(regimes[worst]['return']).strip()}) "
                             f"-- momentum leans on 'up' markets and whipsaws in chop, not all-weather.")
    return {'psr': psr, 'psr_raw': psr_raw, 'psr_active': psr_active,
            'n_trials_used': effective_n_trials(1, family),
            'months': int(len(monthly)), 'regimes': regimes, 'flags': flags}


def _monthly_returns(net):
    """Compound daily net returns into monthly returns -- exactly how robustness() does
    it for the PSR, so the significance test speaks the same monthly language."""
    return net.groupby([net.index.year, net.index.month]).apply(lambda x: (1 + x).prod() - 1)


def _tstat(active):
    """t-stat of the mean of a monthly active-return series (iid assumption)."""
    n = len(active)
    sd = active.std(ddof=1) if n > 1 else 0.0
    return float(active.mean() / (sd / np.sqrt(n))) if sd > 0 else float('nan')


def _nw_tstat(active, lag=3):
    """Newey-West (HAC) t-stat of the same mean. Monthly active returns are autocorrelated
    (momentum unwinds cluster around crashes), which the iid t-stat above ignores; this one
    corrects the variance for it. Reported alongside, never instead of, the plain t."""
    x = np.asarray(active, float)
    n = len(x)
    if n < 2:
        return float('nan')
    d = x - x.mean()
    s = float(d @ d) / n
    for l in range(1, min(lag, n - 1) + 1):
        s += 2 * (1 - l / (lag + 1)) * float(d[l:] @ d[:-l]) / n
    return float(x.mean() / np.sqrt(s / n)) if s > 0 else float('nan')


def _panel_margin(sub_panel, cost_model=ETF_COST):
    """(total-return margin of momentum over EW-universe, monthly active series) on a given
    panel, aligned to a common live window the same way main() does (EW reindexed to
    momentum's window). The active series is what lets a leave-one-name-out run report a
    t-stat rather than the sign of a margin."""
    mom = _first_active(run_panel(sub_panel, target_weights(sub_panel), cost_model))
    ew = _first_active(run_panel(sub_panel, _ew_weights(sub_panel, LOOKBACK), cost_model))
    ew = ew.reindex(mom.index).dropna()
    mom = mom.reindex(ew.index)
    margin = compute_metrics(mom)['total_return'] - compute_metrics(ew)['total_return']
    return margin, (_monthly_returns(mom['net']) - _monthly_returns(ew['net'])).dropna()


def significance_vs_ew(res, ew_res, panel, cost_model=ETF_COST):
    """The gate robustness() was missing: is momentum's edge OVER the EW-universe (not over
    zero) statistically real, or just luck? Works on the monthly ACTIVE return
    (momentum_monthly - ew_monthly) over the shared window.
      * t-stat of the mean monthly active return (need ~2+ to believe it),
      * a seeded 95% bootstrap CI on that mean (10k resamples),
      * % of months momentum beat the EW-universe,
      * the same t with a Newey-West (HAC, lag 3) variance, since monthly active returns
        are autocorrelated,
      * remove-top-contributor: drop each ticker in turn, recompute the margin, and find the
        one name whose removal shrinks momentum's edge the most -- reported as the t-stat
        WITHOUT that name, not as 'still beats' (the sign of a margin is the very point
        comparison this gate exists to replace)."""
    mom_m = _monthly_returns(res['net'])
    ew_m = _monthly_returns(ew_res['net'])
    active = (mom_m - ew_m).dropna()
    n = len(active)
    t = _tstat(active)
    pct_won = float((active > 0).mean())

    rng = np.random.default_rng(0)
    boot_means = active.values[rng.integers(0, n, size=(10000, n))].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])

    full_margin, _ = _panel_margin(panel, cost_model)
    dropped = {tk: _panel_margin(panel.drop(columns=tk), cost_model) for tk in panel.columns}
    # Largest DROP in the edge = smallest margin once that name is gone.
    top = min(dropped, key=lambda tk: dropped[tk][0])
    margin_wo, active_wo = dropped[top]
    return {'t': float(t), 't_nw': _nw_tstat(active), 'n_months': int(n), 'pct_won': pct_won,
            'ci_lo': float(ci_lo), 'ci_hi': float(ci_hi),
            'active_mean': float(active.mean()),
            'top_contributor': top, 'full_margin': float(full_margin),
            'margin_wo': float(margin_wo), 'still_beats': bool(margin_wo > 0),
            't_wo': _tstat(active_wo)}


def panel_verdict(m, m_ew, m_rand, spy_m, flags, sig):
    """The ONE place the panel verdict is decided -- shared by the CLI (main()), the live
    Engine Room (engine_api.run_momentum) and the track-record export, so no caller can
    drift back to a point-comparison 'survives'. Order: raw return bars -> significance
    over the EW-universe (t >= 2) -> robustness flags."""
    beats_ew = bool(m['total_return'] > m_ew['total_return'])
    beats_rand = bool(m['total_return'] > m_rand['total_return'])
    beats_spy = bool(spy_m is None or m['total_return'] > spy_m['total_return'])
    flags = flags or []
    # Three-way gate (plan/14 I0.1, power.py): the statistics decide FAIL (edge ruled out) vs
    # INCONCLUSIVE (can't tell); PASS additionally needs every pre-existing gate below.
    pw = power.from_t(sig['t'], sig['n_months'], ppy=12)
    survives = bool(beats_ew and beats_rand and beats_spy and pw['verdict'] == 'PASS' and not flags)
    verdict = 'PASS' if survives else ('FAIL' if pw['verdict'] == 'FAIL' else 'INCONCLUSIVE')
    why = (f"IR_hat={pw['ir_hat']:.2f}, 95% CI upper {pw['ir_ci_hi']:.2f} vs IR_MIN "
           f"{pw['ir_min']:.2f}; power {pw['power']*100:.0f}% over {pw['years']:.1f}y, "
           f"~{pw['years_for_80pct_power']:.0f}y needed for 80%")
    if verdict == 'FAIL':
        head = f'FAIL -- an edge of IR >= {pw["ir_min"]:.1f} over EW-universe is ruled out ({why}). '
    elif verdict == 'INCONCLUSIVE':
        head = f'INCONCLUSIVE -- ({why}). '
    else:
        head = 'PASS -- '
    if not (beats_ew and beats_rand and beats_spy):
        status = head + 'DOES NOT clear the raw bars -- selection added nothing beyond the universe'
    elif sig['t'] < 2:
        status = (head + 'clears the raw return bars, but the edge over EW-universe is '
                  f'not statistically distinguishable from luck (t={sig["t"]:.2f}, need ~2+)'
                  + (f'; also {len(flags)} robustness flag(s) above.' if flags else '.'))
    elif flags:
        status = (head + f'clears the raw bars and the edge over EW-universe is significant '
                  f'(t={sig["t"]:.2f}), but {len(flags)} robustness flag(s) above temper it.')
    else:
        status = (head + 'SURVIVES the panel bar; robustness-checked with no red flag and the edge '
                  f'over EW-universe is significant (t={sig["t"]:.2f}). '
                  f'Awaiting Tenzing sign-off (economic story).')
    return {
        'survives': survives,
        'verdict': verdict,          # PASS / FAIL / INCONCLUSIVE
        'power': pw,                 # ir_hat, years, ir_ci_hi, power, years_for_80pct_power
        'status': status,
        'beats_ew': beats_ew, 'beats_random': beats_rand, 'beats_spy': beats_spy,
        't_active': float(sig['t']), 'ci': [float(sig['ci_lo']), float(sig['ci_hi'])],
        'pct_won': float(sig['pct_won']), 'top_contributor': sig['top_contributor'],
    }


def sweep(panel, cost_model=ETF_COST):
    """SENSITIVITY, not selection. Run the canonical spec's NEIGHBORS (lookback x top_n) and
    report the WHOLE neighborhood vs the EW-universe over each spec's own window. We do NOT
    pick the winner -- the pre-registered 12mo/top-10 stays the verdict (see main()). The only
    question this answers: is the edge broad (robust) or a single knife-edge config (a fluke)?

    Each neighbor reports the monthly-active t-stat against its OWN EW-universe, the same
    statistic `significance_vs_ew` applies to the canonical spec. `beats_ew` (the sign of a
    total-return margin) stays as a DISPLAY column only: "7/9 beat EW" is seven coin flips
    landing heads by margins the size of noise, and reading it as breadth was exactly the
    mistake audit 4.3 found."""
    out = []
    for lbl, lb in SWEEP_LOOKBACKS.items():
        ew_res = _first_active(run_panel(panel, _ew_weights(panel, lb), cost_model))
        for tn in SWEEP_TOP_NS:
            res = _first_active(run_panel(panel, target_weights(panel, top_n=tn, lookback=lb),
                                          cost_model))
            m = compute_metrics(res)
            ew_win = ew_res.reindex(res.index).dropna()
            ewm = compute_metrics(ew_win)
            active = (_monthly_returns(res['net']) - _monthly_returns(ew_win['net'])).dropna()
            n = len(active)
            sd = active.std(ddof=1) if n > 1 else 0.0
            out.append({
                'lookback': lbl, 'top_n': tn,
                'total_return': m['total_return'], 'cagr': m['cagr'],
                'sharpe': m['sharpe'], 'max_dd': m['max_drawdown'],
                'beats_ew': bool(m['total_return'] > ewm['total_return']),
                't_active': float(active.mean() / (sd / np.sqrt(n))) if sd > 0 else float('nan'),
                'pct_won': float((active > 0).mean()) if n else float('nan'),
                'n_months': int(n),
                'canonical': bool(lb == LOOKBACK and tn == TOP_N),
            })
    return out


def main():
    args = sys.argv[1:]
    log = '--log' in args                       # opt-in: record the Thesis-001 verdict
    args = [a for a in args if a != '--log']
    paths = args or sorted(glob.glob('realdata/*.csv'))
    stock_paths = [p for p in paths
                   if os.path.splitext(os.path.basename(p))[0] not in EXCLUDE]
    if not stock_paths:
        print("No stock CSVs found. Run fetch_universe.py first.")
        return
    panel = load_panel(stock_paths)

    # Thesis 001, canonical spec.
    res = _first_active(run_panel(panel, target_weights(panel)))
    window = res.index

    # Baseline 1: hold SPY over the identical live window (net of the same cost model).
    spy_close_full = (load_csv('realdata/spy.csv', warn=False)['close']
                      if os.path.exists('realdata/spy.csv') else None)
    spy_m = None
    if spy_close_full is not None:
        spy = spy_close_full.reindex(window).dropna()
        spy_pos = pd.Series(1.0, index=spy.index)
        from backtest import run_backtest
        _, spy_m = run_backtest(spy, spy_pos, ETF_COST)

    # Baseline 1b: hold MTUM (momentum factor ETF) over the identical live window.
    mtum_close_full = (load_csv('realdata/mtum.csv', warn=False)['close']
                       if os.path.exists('realdata/mtum.csv') else None)
    mtum_m = None
    if mtum_close_full is not None:
        mtum = mtum_close_full.reindex(window).dropna()
        mtum_pos = pd.Series(1.0, index=mtum.index)
        from backtest import run_backtest
        _, mtum_m = run_backtest(mtum, mtum_pos, ETF_COST)

    # Baseline 2: equal-weight ALL eligible names (the universe itself, same costs).
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
    ew_res = _first_active(run_panel(panel, ew.ffill().fillna(0.0)))
    ew_res = ew_res.reindex(window).dropna()

    # Baseline 3: random TOP_N picks each month, same machinery and costs.
    rng = np.random.default_rng(1)
    rand_res = _first_active(run_panel(
        panel, target_weights(panel, picker=lambda row: rng.choice(
            row.index, size=TOP_N, replace=False))))
    rand_res = rand_res.reindex(window).dropna()

    m = compute_metrics(res)
    m_ew = compute_metrics(ew_res)
    m_rand = compute_metrics(rand_res)

    # Ledger it BEFORE the robustness gauntlet below reads the ledger's trial count, so a
    # fresh ledger's count for this family is exactly 1 (the canonical spec) on a first run.
    ledger.log_experiment(LEDGER_FAMILY, "xsect_momentum_12_1",
                          {"lookback": LOOKBACK, "skip": SKIP, "top_n": TOP_N},
                          sorted(panel.columns), data_paths=stock_paths,
                          result={"total_return": m["total_return"], "sharpe": m["sharpe"]})

    n_names = panel.shape[1]
    print(f"\nCROSS-SECTIONAL MOMENTUM (Thesis 001) -- 12-1, monthly, top {TOP_N} of "
          f"{n_names} stocks, long-only, equal weight")
    print(f"Live window: {window[0].date()} -> {window[-1].date()} "
          f"({len(window)} bars). Net of LIQUID-ETF costs (3/1 bps) on full turnover. "
          f"n_trials=1 (canonical spec, no grid).\n")
    hdr = f"  {'portfolio':22s} {'total ret':>10s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s} {'trades':>7s}"
    print(hdr)
    print("  " + "-" * 68)

    def line(name, mm):
        print(f"  {name:22s} {_pct(mm['total_return'])} {mm['cagr']*100:7.1f}% "
              f"{mm['sharpe']:7.2f} {_pct(mm['max_drawdown'])} {mm['num_trades']:7d}")

    line('momentum top-10', m)
    line('EW universe (all)', m_ew)
    line('random top-10', m_rand)
    if spy_m is not None:
        line('hold SPY', spy_m)
    if mtum_m is not None:
        line('hold MTUM', mtum_m)

    # Per-year split: a one-year-wonder is the classic way a fake edge hides.
    print("\nPer-year net return (momentum vs EW universe -- selection skill by year):")
    for yr, g in res.groupby(res.index.year):
        mo = (1 + g['net']).prod() - 1
        ge = ew_res.reindex(g.index).dropna()
        ewr = (1 + ge['net']).prod() - 1 if len(ge) else float('nan')
        mark = '+' if mo > ewr else '-'
        print(f"    {yr}: momentum {_pct(mo)}   EW {_pct(ewr)}   [{mark}]")

    # ROBUSTNESS GAUNTLET -- the same skeptic's checks the single-name scan applies, so the
    # one surviving candidate is scrutinised BEFORE any human signs off on it (shared with the
    # track-record export via robustness()).
    rob = robustness(res, spy_close_full, ew_res=ew_res, family=LEDGER_FAMILY)
    regimes, flags = rob['regimes'], rob['flags']
    print("\nROBUSTNESS (same gauntlet as the scan):")
    print(f"  Probabilistic Sharpe (monthly ACTIVE vs EW-universe, {rob['months']} months, "
          f"N={rob['n_trials_used']}): "
          f"{rob['psr']:.2f}  (P the edge over EW is > 0; >=0.95 = significant)")
    print(f"    [vs zero, for reference only: {rob['psr_raw']:.2f} -- owning any rising "
          f"basket scores ~1.00, which is why it is not the gate]")
    if regimes:
        print("  Net return by SPY regime (raw, then vs the EW-universe -- only the")
        print("  active column says anything: a long-only book leans 'up' by construction):")
        for r in ('up', 'down', 'chop'):
            act = regimes[r].get('active')
            print(f"    {r:4s}: {_pct(regimes[r]['return'])}   vs EW {_pct(act) if act is not None else '     n/a'}"
                  f"  ({regimes[r]['bars']} bars)")
    if flags:
        print("  RED FLAGS:")
        for f in flags:
            print(f"    - {f}")
    else:
        print("  No robustness red flag fired (the survivorship caveat below still stands).")

    # SIGNIFICANCE VS EW-UNIVERSE -- the gate robustness() was missing. PSR asks "does momentum
    # make money?"; this asks "does momentum beat just owning the universe?" (the honest bar).
    sig = significance_vs_ew(res, ew_res, panel)
    print("\nSIGNIFICANCE VS EW-UNIVERSE (the missing gate):")
    print(f"  Monthly active return (momentum - EW), {sig['n_months']} months:")
    print(f"    t-stat: {sig['t']:.2f}  (need ~2+ to believe the edge is real, not luck)"
          f"   Newey-West (HAC, lag 3): {sig['t_nw']:.2f}")
    print(f"    mean active/mo: {sig['active_mean']*100:.2f}%   "
          f"95% bootstrap CI [{sig['ci_lo']*100:.2f}%, {sig['ci_hi']*100:.2f}%]")
    print(f"    months won: {sig['pct_won']*100:.0f}%  (coin-flip is 50%)")
    print(f"  Remove top contributor ({sig['top_contributor']}): "
          f"t = {sig['t']:.2f} -> {sig['t_wo']:.2f} without it  "
          f"(margin {sig['full_margin']*100:.1f}% -> {sig['margin_wo']*100:.1f}%)")

    # SENSITIVITY SWEEP -- neighbors of the canonical spec, to show it is not a knife-edge fluke.
    sw = sweep(panel)
    n_beat = sum(s['beats_ew'] for s in sw)
    n_sig = sum(s['t_active'] >= 2 for s in sw)
    best_t = max(s['t_active'] for s in sw)
    print("\nSENSITIVITY (neighbors of the canonical spec -- NOT selection; the pre-registered")
    print(f"  12mo/top-10 stays the verdict). {n_sig}/{len(sw)} neighbours significant "
          f"(t >= 2); best t = {best_t:.2f}.")
    print(f"  ({n_beat}/{len(sw)} beat their EW-universe on total return -- display only: the")
    print("   sign of a margin is a coin flip, not breadth.)")
    print(f"    {'lookback':>8s} {'topN':>5s} {'total ret':>10s} {'Sharpe':>7s} "
          f"{'t active':>8s} {'won':>5s} {'beats EW':>9s}")
    for s in sw:
        star = '  <= canonical' if s['canonical'] else ''
        print(f"    {s['lookback']:>8s} {s['top_n']:>5d} {_pct(s['total_return'])} "
              f"{s['sharpe']:7.2f} {s['t_active']:8.2f} {s['pct_won']*100:4.0f}% "
              f"{'YES' if s['beats_ew'] else 'no':>9s}{star}")

    print("\nThe bar that matters:")
    pv = panel_verdict(m, m_ew, m_rand, spy_m, flags, sig)
    beats_ew, beats_rand, beats_spy = pv['beats_ew'], pv['beats_random'], pv['beats_spy']
    print(f"  beats EW universe:  {'YES' if beats_ew else 'NO'}   "
          f"(selection skill vs just owning these names)")
    print(f"  beats random picks: {'YES' if beats_rand else 'NO'}")
    print(f"  beats holding SPY:  {'YES' if beats_spy else 'NO'}")
    pw = pv['power']
    print(f"\nPOWER / THREE-WAY GATE (active vs EW-universe, IR_MIN = {pw['ir_min']:.2f}):")
    print(f"  annualized IR_hat {pw['ir_hat']:.2f} over {pw['years']:.1f} years   observed t {pw['t']:.2f}")
    print(f"  95% CI upper bound on IR: {pw['ir_ci_hi']:.2f}  "
          f"({'< IR_MIN: edge ruled out' if pw['ir_ci_hi'] < pw['ir_min'] else '>= IR_MIN: edge NOT ruled out'})")
    print(f"  power P(t >= 2 | true IR = {pw['ir_min']:.2f}): {pw['power']*100:.0f}%   "
          f"years needed for 80% power: {pw['years_for_80pct_power']:.1f}")
    print(f"  three-way verdict: {pv['verdict']}")

    print("\nCAVEATS (read before believing anything above):")
    print(f"  * SURVIVORSHIP: the universe is today's {n_names} liquid names -- every one")
    print("    survived to 2026 by construction. This inflates ALL long-only rows above,")
    print("    which is why 'beats EW universe' is the honest bar, not the raw return.")
    print("  * Single history, no folds: there is nothing to fit (n_trials=1), but this is")
    print("    still ONE draw of history -- the per-year split, regime split, and probabilistic")
    print("    Sharpe above ARE that scrutiny; a live paper-trade is the real out-of-sample test.")
    print(f"\nVERDICT: {pv['status']}\n")

    # Record one panel verdict into the shared log. The logger stays a pure recorder --
    # every field here already came out of compute_metrics / robustness above. The honest
    # bar for a survivorship-inflated panel is the EW-universe, so that (not buy&hold) is the
    # 'vs B&H' column; PSR stands in for the deflated Sharpe a single-name run would carry.
    if log:
        clean = pv['survives']
        append_verdict({
            "ticker": f"panel_{n_names}", "strategy": "xsect_momentum_12_1",
            "cost_regime": "3/1 bps (liquid ETF)", "run": "panel",
            "oos_total_return": m["total_return"], "oos_sharpe": m["sharpe"],
            "oos_max_dd": m["max_drawdown"], "num_trades": m["num_trades"],
            "buy_hold_return": m_ew["total_return"],       # EW-universe = the honest bar
            "spy_return": spy_m["total_return"] if spy_m is not None else None,
            "beats_bh": bool(beats_ew),
            "deflated_sharpe": rob["psr"], "trades_per_fold": None,
            "regime_split": regimes, "red_flags": flags, "clean": clean,
            "synthetic": False,
        })
        print("Logged 1 Thesis-001 panel verdict to verdicts.jsonl.\n")


if __name__ == '__main__':
    main()
