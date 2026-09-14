"""Cross-sectional momentum panel backtest -- Thesis 001 (Jonathan).

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
from diagnostics import deflated_sharpe_ratio, regime_split
from verdict_log import append_verdict

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


def target_weights(panel, top_n=TOP_N, lookback=LOOKBACK, picker=None):
    """Daily target-weight DataFrame: at each month-end, long the top_n names by 12-1
    momentum (equal weight), hold until the next rebalance. `picker` overrides the
    selection (used by the random baseline); it gets (scores_row) -> list of names.
    `lookback` is exposed only for the robustness sweep -- the canonical spec uses the default."""
    scores = momentum_12_1(panel, lookback=lookback)
    rebal = month_end_mask(panel.index)
    w = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for t in panel.index[rebal]:
        row = scores.loc[t].dropna()
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


def _ew_weights(panel, lookback):
    """Equal-weight ALL names that have a valid momentum score at each month-end -- the
    'just own the universe' baseline for a given lookback (eligibility tracks the lookback)."""
    scores = momentum_12_1(panel, lookback=lookback)
    rebal = month_end_mask(panel.index)
    w = pd.DataFrame(np.nan, index=panel.index, columns=panel.columns)
    for t in panel.index[rebal]:
        row = scores.loc[t].dropna()
        if len(row) < 1:
            continue
        wt = pd.Series(0.0, index=panel.columns)
        wt[row.index] = 1.0 / len(row)
        w.loc[t] = wt
    return w.ffill().fillna(0.0)


def robustness(res, spy_close):
    """The scan's gauntlet applied to one panel result -> {psr, months, regimes, flags}.
    Shared by the CLI and the track-record export so both tell the SAME story. Probabilistic
    Sharpe is scored on MONTHLY returns (a monthly strategy: daily bars would count ~21
    held-flat days as 21 independent wins and overstate significance)."""
    monthly = res['net'].groupby([res.index.year, res.index.month]).apply(
        lambda x: (1 + x).prod() - 1)
    psr = deflated_sharpe_ratio(monthly.values, n_trials=1, ppy=12)   # n=1 => P(Sharpe > 0)
    regimes = regime_split(res['net'], spy_close) if spy_close is not None else None
    flags = []
    if psr == psr and psr < 0.95:
        flags.append(f"Probabilistic Sharpe {psr:.2f} < 0.95 -- not clearly distinguishable from zero.")
    yearly = [(y, (1 + g['net']).prod() - 1) for y, g in res.groupby(res.index.year)]
    ylogs = [(y, np.log(1 + r)) for y, r in yearly if r > -1]
    ytot = sum(l for _, l in ylogs)
    if ytot > 0 and ylogs:
        by, bl = max(ylogs, key=lambda t: t[1])
        if bl / ytot > 0.6:
            flags.append(f"{bl/ytot*100:.0f}% of the (log) return came from {by} -- a one-year wonder.")
    if regimes:
        worst = min(('up', 'down', 'chop'), key=lambda r: regimes[r]['return'])
        if regimes[worst]['return'] < -0.05:     # materially loses money in some regime
            flags.append(f"Loses in the '{worst}' regime ({_pct(regimes[worst]['return']).strip()}) "
                         f"-- momentum leans on 'up' markets and whipsaws in chop, not all-weather.")
    return {'psr': psr, 'months': int(len(monthly)), 'regimes': regimes, 'flags': flags}


def _monthly_returns(net):
    """Compound daily net returns into monthly returns -- exactly how robustness() does
    it for the PSR, so the significance test speaks the same monthly language."""
    return net.groupby([net.index.year, net.index.month]).apply(lambda x: (1 + x).prod() - 1)


def _panel_margin(sub_panel, cost_model=ETF_COST):
    """Total-return margin of momentum over EW-universe on a given panel, aligned to a
    common live window the same way main() does (EW reindexed to momentum's window)."""
    mom = _first_active(run_panel(sub_panel, target_weights(sub_panel), cost_model))
    ew = _first_active(run_panel(sub_panel, _ew_weights(sub_panel, LOOKBACK), cost_model))
    ew = ew.reindex(mom.index).dropna()
    mom = mom.reindex(ew.index)
    return compute_metrics(mom)['total_return'] - compute_metrics(ew)['total_return']


def significance_vs_ew(res, ew_res, panel, cost_model=ETF_COST):
    """The gate robustness() was missing: is momentum's edge OVER the EW-universe (not over
    zero) statistically real, or just luck? Works on the monthly ACTIVE return
    (momentum_monthly - ew_monthly) over the shared window.
      * t-stat of the mean monthly active return (need ~2+ to believe it),
      * a seeded 95% bootstrap CI on that mean (10k resamples),
      * % of months momentum beat the EW-universe,
      * remove-top-contributor: drop each ticker in turn, recompute the margin, and find the
        one name whose removal shrinks momentum's edge the most (does the edge survive it?)."""
    mom_m = _monthly_returns(res['net'])
    ew_m = _monthly_returns(ew_res['net'])
    active = (mom_m - ew_m).dropna()
    n = len(active)
    sd = active.std(ddof=1)
    t = active.mean() / (sd / np.sqrt(n)) if sd > 0 else float('nan')
    pct_won = float((active > 0).mean())

    rng = np.random.default_rng(0)
    boot_means = active.values[rng.integers(0, n, size=(10000, n))].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])

    full_margin = _panel_margin(panel, cost_model)
    margins = {tk: _panel_margin(panel.drop(columns=tk), cost_model) for tk in panel.columns}
    # Largest DROP in the edge = smallest margin once that name is gone.
    top = min(margins, key=margins.get)
    margin_wo = margins[top]
    return {'t': float(t), 'n_months': int(n), 'pct_won': pct_won,
            'ci_lo': float(ci_lo), 'ci_hi': float(ci_hi),
            'active_mean': float(active.mean()),
            'top_contributor': top, 'full_margin': float(full_margin),
            'margin_wo': float(margin_wo), 'still_beats': bool(margin_wo > 0)}


def sweep(panel, cost_model=ETF_COST):
    """SENSITIVITY, not selection. Run the canonical spec's NEIGHBORS (lookback x top_n) and
    report the WHOLE neighborhood vs the EW-universe over each spec's own window. We do NOT
    pick the winner -- the pre-registered 12mo/top-10 stays the verdict (see main()). The only
    question this answers: is the edge broad (robust) or a single knife-edge config (a fluke)?"""
    out = []
    for lbl, lb in SWEEP_LOOKBACKS.items():
        ew_res = _first_active(run_panel(panel, _ew_weights(panel, lb), cost_model))
        for tn in SWEEP_TOP_NS:
            res = _first_active(run_panel(panel, target_weights(panel, top_n=tn, lookback=lb),
                                          cost_model))
            m = compute_metrics(res)
            ewm = compute_metrics(ew_res.reindex(res.index).dropna())
            out.append({
                'lookback': lbl, 'top_n': tn,
                'total_return': m['total_return'], 'cagr': m['cagr'],
                'sharpe': m['sharpe'], 'max_dd': m['max_drawdown'],
                'beats_ew': bool(m['total_return'] > ewm['total_return']),
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
    rob = robustness(res, spy_close_full)
    regimes, flags = rob['regimes'], rob['flags']
    print("\nROBUSTNESS (same gauntlet as the scan):")
    print(f"  Probabilistic Sharpe (monthly, {rob['months']} months): "
          f"{rob['psr']:.2f}  (P the true Sharpe is > 0; >=0.95 = significant)")
    if regimes:
        print("  Net return by SPY regime (a long-only signal is expected to lean 'up'):")
        for r in ('up', 'down', 'chop'):
            print(f"    {r:4s}: {_pct(regimes[r]['return'])}  ({regimes[r]['bars']} bars)")
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
    print(f"    t-stat: {sig['t']:.2f}  (need ~2+ to believe the edge is real, not luck)")
    print(f"    mean active/mo: {sig['active_mean']*100:.2f}%   "
          f"95% bootstrap CI [{sig['ci_lo']*100:.2f}%, {sig['ci_hi']*100:.2f}%]")
    print(f"    months won: {sig['pct_won']*100:.0f}%  (coin-flip is 50%)")
    print(f"  Remove top contributor ({sig['top_contributor']}): "
          f"margin {sig['full_margin']*100:.1f}% -> {sig['margin_wo']*100:.1f}%  "
          f"(momentum {'still beats' if sig['still_beats'] else 'now LOSES to'} EW without it)")

    # SENSITIVITY SWEEP -- neighbors of the canonical spec, to show it is not a knife-edge fluke.
    sw = sweep(panel)
    n_beat = sum(s['beats_ew'] for s in sw)
    print("\nSENSITIVITY (neighbors of the canonical spec -- NOT selection; the pre-registered")
    print(f"  12mo/top-10 stays the verdict). {n_beat}/{len(sw)} neighbor specs beat their EW-universe:")
    print(f"    {'lookback':>8s} {'topN':>5s} {'total ret':>10s} {'Sharpe':>7s} {'beats EW':>9s}")
    for s in sw:
        star = '  <= canonical' if s['canonical'] else ''
        print(f"    {s['lookback']:>8s} {s['top_n']:>5d} {_pct(s['total_return'])} "
              f"{s['sharpe']:7.2f} {'YES' if s['beats_ew'] else 'no':>9s}{star}")

    print("\nThe bar that matters:")
    beats_ew = m['total_return'] > m_ew['total_return']
    beats_rand = m['total_return'] > m_rand['total_return']
    beats_spy = spy_m is None or m['total_return'] > spy_m['total_return']
    print(f"  beats EW universe:  {'YES' if beats_ew else 'NO'}   "
          f"(selection skill vs just owning these names)")
    print(f"  beats random picks: {'YES' if beats_rand else 'NO'}")
    print(f"  beats holding SPY:  {'YES' if beats_spy else 'NO'}")

    print("\nCAVEATS (read before believing anything above):")
    print(f"  * SURVIVORSHIP: the universe is today's {n_names} liquid names -- every one")
    print("    survived to 2026 by construction. This inflates ALL long-only rows above,")
    print("    which is why 'beats EW universe' is the honest bar, not the raw return.")
    print("  * Single history, no folds: there is nothing to fit (n_trials=1), but this is")
    print("    still ONE draw of history -- the per-year split, regime split, and probabilistic")
    print("    Sharpe above ARE that scrutiny; a live paper-trade is the real out-of-sample test.")
    if not (beats_ew and beats_rand and beats_spy):
        verdict = 'DOES NOT clear the bar -- selection added nothing beyond the universe'
    elif sig['t'] < 2:
        verdict = ('UNPROVEN -- clears the raw return bars, but the edge over EW-universe is '
                   f'not statistically distinguishable from luck (t={sig["t"]:.2f}, need ~2+)'
                   + (f'; also {len(flags)} robustness flag(s) above.' if flags else '.'))
    elif flags:
        verdict = (f'clears the raw bars and the edge over EW-universe is significant '
                   f'(t={sig["t"]:.2f}), but {len(flags)} robustness flag(s) above temper it.')
    else:
        verdict = ('SURVIVES the panel bar; robustness-checked with no red flag and the edge '
                   f'over EW-universe is significant (t={sig["t"]:.2f}). '
                   f'Awaiting Jonathan sign-off (economic story) + Henry judgment.')
    print(f"\nVERDICT: {verdict}\n")

    # Record one panel verdict into the shared log. The logger stays a pure recorder --
    # every field here already came out of compute_metrics / robustness above. The honest
    # bar for a survivorship-inflated panel is the EW-universe, so that (not buy&hold) is the
    # 'vs B&H' column; PSR stands in for the deflated Sharpe a single-name run would carry.
    if log:
        clean = bool(beats_ew and beats_rand and beats_spy and not flags and sig['t'] >= 2)
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
