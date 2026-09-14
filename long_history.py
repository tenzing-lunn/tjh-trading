"""P1.2 -- the century-long momentum test, on Ken French's data instead of ours.

Question: does the top momentum decile beat the market at all, over the longest history
available? This is INDEPENDENT of `xsect.py`: it is French's own 10-portfolios-on-prior-
returns (all NYSE/AMEX/Nasdaq names, value-weighted inside each decile), not our 30-name
or point-in-time universe, so a single universe's survivorship problem cannot explain it.

Active return, monthly, 1927-01 -> now:   Hi PRIOR - (Mkt-RF + RF)
(the top-decile total return minus the total market return that month.)

Inputs, all from fetch_french.py (research_data/french/, gitignored):
    10_portfolios_momentum_monthly.csv   Hi PRIOR = top decile
    ff3_factors_monthly.csv              Mkt-RF, RF
Joined on the intersection of dates -- nothing is padded or imputed.

Costs: this is NOT a backtest of our strategy, so the after-cost number is an ESTIMATE --
assumed turnover (default 435%/yr, our canonical xsect spec) at `costs.py`'s LIQUID-ETF
rate, spread evenly across the months. See the sensitivity table for what a wrong
turnover assumption does.

    python3 long_history.py
"""
import math

import numpy as np
import pandas as pd

from costs import CostModel

FRENCH = 'research_data/french'
ETF_COST = CostModel(spread_bps=3, slippage_bps=1)
TURNOVER_YR = 4.35


def active_series():
    deciles = pd.read_csv(f'{FRENCH}/10_portfolios_momentum_monthly.csv', parse_dates=['date'])
    ff3 = pd.read_csv(f'{FRENCH}/ff3_factors_monthly.csv', parse_dates=['date'])
    df = deciles[['date', 'Hi PRIOR', 'Lo PRIOR']].merge(
        ff3[['date', 'Mkt-RF', 'RF']], on='date', how='inner').set_index('date')
    df['mkt'] = (df['Mkt-RF'] + df['RF']) / 100.0
    df['hi'] = df['Hi PRIOR'] / 100.0
    df['lo'] = df['Lo PRIOR'] / 100.0
    df['active'] = df['hi'] - df['mkt']
    return df


def tstat(x):
    x = np.asarray(x, dtype=float)
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float('nan')
    return x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))


def nw_tstat(x, lags=12):
    """Newey-West t: the plain t assumes independent months, which momentum is not."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    var = (e @ e) / n
    for l in range(1, lags + 1):
        cov = (e[l:] @ e[:-l]) / n
        var += 2 * (1 - l / (lags + 1)) * cov
    return x.mean() / math.sqrt(var / n)


def two_sided_p(t, n):
    """Normal approximation -- n is >=35 in every bucket we report."""
    if not np.isfinite(t):
        return float('nan')
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))


def decade_label(ts):
    return '1927-29' if ts.year < 1930 else f"{(ts.year // 10) * 10}s"


def decade_table(active):
    rows = []
    total = active.sum()
    for label, grp in active.groupby(active.index.map(decade_label), sort=True):
        rows.append({
            'decade': label,
            'n': len(grp),
            'mean_monthly_pct': grp.mean() * 100,
            'annualized_pct': grp.mean() * 12 * 100,
            't': tstat(grp),
            'sum_pct': grp.sum() * 100,
            'share_of_total': grp.sum() / total if total else float('nan'),
        })
    return pd.DataFrame(rows).set_index('decade')


def drawdowns(cum, top=5):
    """Peak-to-trough episodes of a cumulative (arithmetic) active-return path."""
    peak = cum.cummax()
    dd = cum - peak
    episodes, start, trough_i = [], None, None
    for i, (date, d) in enumerate(dd.items()):
        if d < -1e-12 and start is None:
            start = i
            trough_i = i
        elif d < -1e-12:
            if d < dd.iloc[trough_i]:
                trough_i = i
        elif start is not None:
            episodes.append((dd.index[start], dd.index[trough_i], date, dd.iloc[trough_i]))
            start, trough_i = None, None
    if start is not None:
        episodes.append((dd.index[start], dd.index[trough_i], None, dd.iloc[trough_i]))
    episodes.sort(key=lambda e: e[3])
    return episodes[:top]


def main():
    df = active_series()
    a = df['active']
    n = len(a)
    print(f"Top-decile momentum minus market: {a.index[0]:%Y-%m} -> {a.index[-1]:%Y-%m}  "
          f"({n} months, {n/12:.1f} years)")

    drag = (TURNOVER_YR / 12) * float(ETF_COST.cost_fraction([1.0])[0])
    net = a - drag
    print(f"\nAssumed cost drag: {TURNOVER_YR*100:.0f}%/yr turnover x "
          f"{ETF_COST.cost_fraction([1.0])[0]*1e4:.1f} bps/unit = "
          f"{drag*1e4:.2f} bps/month ({drag*12*100:.2f} %/yr)")

    for name, s in (('GROSS', a), ('NET (est.)', net)):
        t = tstat(s)
        print(f"\n{name}: mean {s.mean()*100:.4f} %/mo  ({s.mean()*12*100:.2f} %/yr)  "
              f"sd {s.std(ddof=1)*100:.2f}  t = {t:.2f}  p = {two_sided_p(t, len(s)):.4f}  "
              f"ann. IR {s.mean()/s.std(ddof=1)*math.sqrt(12):.2f}  "
              f"Newey-West(12) t = {nw_tstat(s):.2f}")

    hi_w, mkt_w = (1 + df['hi']).prod(), (1 + df['mkt']).prod()
    print(f"\nCompounded over the window: top decile x{hi_w:,.0f}, market x{mkt_w:,.0f} "
          f"({(hi_w/mkt_w):,.1f}x the market, gross)")

    print("\n--- per decade (gross) ---")
    g = decade_table(a)
    print(g.to_string(float_format=lambda v: f"{v:8.3f}"))
    print("\n--- per decade (net, estimated) ---")
    print(decade_table(net).to_string(float_format=lambda v: f"{v:8.3f}"))

    worst = g['share_of_total'].abs().idxmax()
    print(f"\nLargest single-decade share of the total gross gain: {worst} "
          f"{g.loc[worst, 'share_of_total']*100:.1f}%  "
          f"(>50% would fail Gate G1 criterion 1)")

    print("\n--- worst single months (active) ---")
    print((a.sort_values().head(10) * 100).to_string(float_format=lambda v: f"{v:7.2f}"))

    print("\n--- worst drawdowns of the cumulative active path (arithmetic, pp) ---")
    cum = a.cumsum()
    for start, trough, end, depth in drawdowns(cum, top=6):
        rec = f"{end:%Y-%m}" if end is not None else "not recovered"
        print(f"  {start:%Y-%m} -> trough {trough:%Y-%m} ({depth*100:7.1f} pp), recovered {rec}")

    print("\n--- worst drawdowns of relative wealth (top decile / market, compounded, %) ---")
    rel = np.log1p(df['hi']) - np.log1p(df['mkt'])
    for start, trough, end, depth in drawdowns(rel.cumsum(), top=6):
        rec = f"{end:%Y-%m}" if end is not None else "not recovered"
        print(f"  {start:%Y-%m} -> trough {trough:%Y-%m} ({(math.exp(depth)-1)*100:7.1f} %), "
              f"recovered {rec}")

    print("\n--- known crash windows ---")
    for label, lo, hi in (('1932 reversal', '1932-06', '1933-12'),
                          ('2009 reversal', '2009-01', '2009-12'),
                          ('2020 covid', '2020-01', '2020-12')):
        w = a.loc[lo:hi]
        print(f"  {label} {lo}..{hi}: sum {w.sum()*100:7.1f} pp, "
              f"worst month {w.min()*100:6.1f}% in {w.idxmin():%Y-%m}")

    print("\n--- sub-periods (gross) ---")
    for label, lo in (('full', '1927-01'), ('post-1963 (CRSP-quality data)', '1963-01'),
                      ('post-1993 (after Jegadeesh-Titman published)', '1993-01'),
                      ('post-2000', '2000-01'), ('post-2010', '2010-01')):
        s = a.loc[lo:]
        print(f"  {label:44s} n={len(s):4d}  {s.mean()*12*100:6.2f} %/yr  t = {tstat(s):5.2f}")

    print("\n--- cost sensitivity: net %/yr and t, vs turnover x cost-per-unit-turnover ---")
    modern = float(ETF_COST.cost_fraction([1.0])[0]) * 1e4
    print(f"  {'turnover':>10s} " + ' '.join(f"{c:>18s}" for c in
          (f"{modern:.1f} bps (today)", "20 bps", "50 bps (pre-1975)")))
    for turn in (2.0, 4.35, 8.0, 12.0, 24.0):
        cells = []
        for bps in (modern, 20.0, 50.0):
            s = a - (turn / 12) * bps / 1e4
            cells.append(f"{s.mean()*12*100:7.2f} / t={tstat(s):5.2f}")
        print(f"  {turn*100:8.0f}%/yr " + ' '.join(f"{c:>18s}" for c in cells))


if __name__ == '__main__':
    main()
