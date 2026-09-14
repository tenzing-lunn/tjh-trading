"""Bar-by-bar backtest with NO LOOKAHEAD.

Convention: positions[t] is the target weight decided using information available
up to and including bar t's close. The return you actually earn on bar t is the
position you were ALREADY holding (decided at t-1) times bar t's return.
That is enforced by held = positions.shift(1). This is the single most common
place beginners cheat by accident -- so it is baked into the engine, not the strategy."""
import pandas as pd
from metrics import compute_metrics


def run_backtest(prices, positions, cost_model, periods_per_year=None):
    """`periods_per_year` None -> inferred from prices.index (metrics.infer_ppy)."""
    prices = prices.astype(float)
    rets = prices.pct_change().fillna(0.0)
    pos = positions.reindex(prices.index).fillna(0.0).clip(-1, 1)
    held = pos.shift(1).fillna(0.0)                       # <-- no lookahead
    turnover = (pos - pos.shift(1)).abs().fillna(pos.abs())
    costs = pd.Series(cost_model.cost_fraction(turnover.values), index=prices.index)
    gross = held * rets
    net = gross - costs
    out = pd.DataFrame({'ret':rets,'pos':pos,'held':held,'turnover':turnover,
                        'gross':gross,'cost':costs,'net':net})
    out['equity'] = (1 + net).cumprod()
    return out, compute_metrics(out, periods_per_year)
