"""Performance metrics. Equity is recomputed from net returns so this works on
any slice of a backtest (needed for walk-forward fold scoring)."""
import numpy as np


def compute_metrics(df, ppy=252):
    net = df['net'].values
    n = len(net)
    if n == 0:
        return {k: np.nan for k in
                ['total_return','cagr','sharpe','ann_vol','max_drawdown',
                 'num_trades','avg_turnover','win_rate','ev_per_trade_frac','bars']}
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


def active_metrics(df, bench_df, ppy=252):
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
    rs = df['net'].reindex(a.index).values
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
