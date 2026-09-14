"""Walk-forward validation -- the defense against curve-fitting.
For each test fold, parameters are chosen using ONLY prior (train) data; performance
is then recorded on the unseen test fold. Causal rolling windows mean positions can be
computed on the full series; only PARAMETER SELECTION must respect the boundary."""
import numpy as np
import pandas as pd
from backtest import run_backtest
from metrics import compute_metrics, infer_ppy


def walk_forward(prices, strat_factory, param_grid, cost_model,
                 n_folds=5, ppy=None, select='sharpe'):
    if ppy is None:                  # once, from the FULL series -- fold slices reuse it
        ppy = infer_ppy(prices.index)
    precomp = {}
    for i, params in enumerate(param_grid):
        out, _ = run_backtest(prices, strat_factory(params)(prices), cost_model, ppy)
        precomp[i] = out

    idx = prices.index
    fold = len(idx) // (n_folds + 1)
    rows, chosen = [], []
    for k in range(1, n_folds + 1):
        tr = idx[:fold * k]
        te = idx[fold * k: fold * (k + 1)]
        if len(te) < 5:
            break
        best = None
        for i, params in enumerate(param_grid):
            sc = compute_metrics(precomp[i].loc[tr], ppy)[select]
            if sc == sc and (best is None or sc > best[0]):   # sc==sc filters NaN
                best = (sc, i, params)
        i_best = best[1] if best else 0
        chosen.append(param_grid[i_best])
        rows.append(precomp[i_best].loc[te, ['net', 'held', 'turnover']])

    combined = pd.concat(rows).sort_index() if rows else pd.DataFrame(
        columns=['net', 'held', 'turnover'])
    return combined, chosen
