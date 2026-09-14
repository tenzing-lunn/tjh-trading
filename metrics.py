"""Performance metrics. Equity is recomputed from net returns so this works on
any slice of a backtest (needed for walk-forward fold scoring)."""
import numpy as np
import pandas as pd

DAILY_PPY = 252           # trading days per year
SESSION_MINUTES = 390     # US regular session, 09:30-16:00


def infer_ppy(index):
    """Periods-per-year from a DatetimeIndex's median bar spacing (the same approach as
    forecast_kronos.infer_step). Counts TRADING time, not calendar time:
      daily -> 252;  weekly -> 52;  monthly -> 12;
      intraday k-minute regular-session bars -> 252 * 390 / k  (1-min 98,280; 5-min 19,656;
      hourly 1,638).
    Raises ValueError instead of guessing when the spacing is irregular, falls between
    buckets, or the bars look like extended hours (more bars per day than a regular session
    holds) -- pass an explicit ppy in those cases."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError(f"cannot infer ppy from a {type(index).__name__}; pass ppy explicitly")
    if len(index) < 3:
        raise ValueError(f"cannot infer ppy from {len(index)} bars; pass ppy explicitly")
    if not index.is_monotonic_increasing:
        raise ValueError("cannot infer ppy from an unsorted index; pass ppy explicitly")
    diffs = pd.Series(index).diff().dropna()
    step = diffs.median()
    days = step / pd.Timedelta(days=1)
    if step < pd.Timedelta(hours=20):
        minutes = step / pd.Timedelta(minutes=1)
        if minutes != int(minutes) or not 1 <= minutes <= SESSION_MINUTES:
            raise ValueError(f"intraday bar spacing {step} is not a whole number of minutes "
                             f"within one session; pass ppy explicitly")
        if (diffs == step).mean() < 0.5:
            raise ValueError(f"irregular intraday spacing (median {step} covers <50% of bars); "
                             f"pass ppy explicitly")
        per_session = SESSION_MINUTES / minutes
        per_day = pd.Series(1, index=index).groupby(index.normalize()).size().median()
        if per_day > np.ceil(per_session) + 1:
            raise ValueError(f"{per_day:.0f} bars/day exceeds a {SESSION_MINUTES}-min regular "
                             f"session at {step} bars (extended hours?); pass ppy explicitly")
        ppy = DAILY_PPY * SESSION_MINUTES / minutes
        return int(ppy) if ppy == int(ppy) else ppy
    if 0.8 <= days <= 4:
        return DAILY_PPY
    if 5 <= days <= 9:
        return 52
    if 25 <= days <= 35:
        return 12
    raise ValueError(f"bar spacing {step} matches no known frequency; pass ppy explicitly")


def compute_metrics(df, ppy=None):
    """`ppy` None -> inferred from df.index (infer_ppy); an explicit value always wins."""
    net = df['net'].values
    n = len(net)
    if n == 0:
        return {k: np.nan for k in
                ['total_return','cagr','sharpe','ann_vol','max_drawdown',
                 'num_trades','avg_turnover','win_rate','ev_per_trade_frac','bars']}
    if ppy is None:
        ppy = infer_ppy(df.index)
    eq = np.cumprod(1 + net)
    total_return = eq[-1] - 1
    years = n / ppy
    cagr = eq[-1] ** (1 / years) - 1 if years > 0 and eq[-1] > 0 else np.nan
    vol = net.std(ddof=1) * np.sqrt(ppy) if n > 1 else np.nan
    sharpe = (net.mean() * ppy) / vol if vol and vol > 0 else np.nan
    peak = np.maximum.accumulate(eq)
    max_dd = (eq / peak - 1).min()
    turn = df['turnover'].values if 'turnover' in df else np.zeros(n)
    trades = int((turn > 1e-9).sum())
    held = df['held'].abs().values if 'held' in df else np.ones(n)
    active = held > 1e-9
    win_rate = (net[active] > 0).sum() / active.sum() if active.sum() > 0 else np.nan
    ev = net.sum() / trades if trades > 0 else np.nan
    return {'total_return':total_return,'cagr':cagr,'sharpe':sharpe,'ann_vol':vol,
            'max_drawdown':max_dd,'num_trades':trades,'avg_turnover':turn.mean(),
            'win_rate':win_rate,'ev_per_trade_frac':ev,'bars':n}


def active_metrics(df, bench_df, ppy=None):
    """Benchmark-relative metrics: how much of this is skill and how much is just the
    benchmark? `bench_df` is the benchmark's backtest output under the SAME cost model;
    the two are aligned on their shared index and bars missing on either side are dropped.

    Every series used here is 'net' (cost-adjusted) -- beta and alpha included -- so that
    alpha_ann + beta*benchmark reconstructs exactly the return the strategy actually earned,
    costs and all. A beta near 1 with alpha_ann near 0 means "this is the benchmark".

    Returns {'active_return' (compounded), 'tracking_error' (annualized), 'information_ratio',
    't_stat' (of the mean active return), 'beta', 'alpha_ann', 'pct_bars_won', 'bars'}."""
    a = (df['net'] - bench_df['net'].reindex(df.index)).dropna()
    n = len(a)
    keys = ['active_return','tracking_error','information_ratio','t_stat',
            'beta','alpha_ann','pct_bars_won']
    if n < 2:
        return dict({k: np.nan for k in keys}, bars=n)
    if ppy is None:
        ppy = infer_ppy(a.index)
    rs =df['net'].reindex(a.index).values
    rb = bench_df['net'].reindex(a.index).values
    av = a.values
    sd = av.std(ddof=1)
    te = sd * np.sqrt(ppy)
    var_b = rb.var(ddof=1)
    beta = np.cov(rs, rb, ddof=1)[0, 1] / var_b if var_b > 0 else np.nan
    return {'active_return': float(np.prod(1 + av) - 1),
            'tracking_error': float(te),
            'information_ratio': float(av.mean() * ppy / te) if te > 0 else np.nan,
            't_stat': float(av.mean() / (sd / np.sqrt(n))) if sd > 0 else np.nan,
            'beta': float(beta),
            'alpha_ann': float((rs.mean() - beta * rb.mean()) * ppy),
            'pct_bars_won': float((av > 0).mean()),
            'bars': n}
