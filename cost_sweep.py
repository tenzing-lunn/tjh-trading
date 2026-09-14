"""Cost sweep for Thesis 001 -- run canonical spec at 3/10/25/50 bps total cost.
Each cost level uses spread_bps=total_cost, slippage_bps=0 for simplicity and
consistency (all basis points allocated to spread, zero slippage).
"""
import glob
import os
import sys

import numpy as np
import pandas as pd

from costs import CostModel
from data import load_csv
from metrics import compute_metrics
from xsect import (
    load_panel, EXCLUDE, TOP_N, LOOKBACK, target_weights, _ew_weights,
    run_panel, _first_active
)


def main():
    # Load the realdata/ panel (same as xsect.py main()).
    paths = sorted(glob.glob('realdata/*.csv'))
    stock_paths = [p for p in paths
                   if os.path.splitext(os.path.basename(p))[0] not in EXCLUDE]
    if not stock_paths:
        print("No stock CSVs found. Run fetch_universe.py first.")
        return
    panel = load_panel(stock_paths)

    # Build the canonical weights once (no cost dependence).
    mom_weights = target_weights(panel)
    ew_weights_obj = _ew_weights(panel, LOOKBACK)

    # Test four cost regimes: 3, 10, 25, 50 bps (spread_bps=total, slippage_bps=0).
    cost_levels = [3, 10, 25, 50]
    results = []

    print("\nCOST SWEEP: Canonical Thesis 001 spec (12-1, monthly, top-10, EW-universe baseline)")
    print(f"Universe: {panel.shape[1]} stocks")
    print("Cost allocation: all basis points as spread_bps, slippage_bps=0")
    print("(i.e., 3 bps = spread_bps=3/slippage_bps=0; effective cost per unit turnover = 0.5*spread_bps)\n")
    print("Note: xsect.py canonical run uses 3/1 bps (spread=3, slip=1, effective=2.5 bps per turnover)")
    print("      which gives momentum return of 309.4%. This sweep's 3 bps uses different split (3/0).\n")

    for cost_bps in cost_levels:
        cost_model = CostModel(spread_bps=cost_bps, slippage_bps=0.0)

        # Run momentum and EW strategies through the same window.
        mom_res = _first_active(run_panel(panel, mom_weights, cost_model))
        ew_res = _first_active(run_panel(panel, ew_weights_obj, cost_model))

        # Align to common window.
        window = mom_res.index
        ew_res = ew_res.reindex(window).dropna()
        mom_res = mom_res.reindex(ew_res.index)

        # Compute metrics.
        m_mom = compute_metrics(mom_res)
        m_ew = compute_metrics(ew_res)

        mom_ret = m_mom['total_return']
        ew_ret = m_ew['total_return']
        margin = mom_ret - ew_ret
        beats_ew = margin > 0

        results.append({
            'cost_bps': cost_bps,
            'mom_total_return': mom_ret,
            'ew_total_return': ew_ret,
            'margin': margin,
            'beats_ew': beats_ew,
        })

    # Print table.
    print("Cost level | Momentum total return | EW-universe total return | Margin | Beats EW?")
    print("-" * 90)
    for r in results:
        print(f"{r['cost_bps']:>3d} bps     | {r['mom_total_return']*100:>20.1f}% | {r['ew_total_return']*100:>24.1f}% | "
              f"{r['margin']*100:>6.1f}% | {'YES' if r['beats_ew'] else 'NO'}")

    # Find the cost level where margin turns negative.
    negative_margins = [r for r in results if r['margin'] <= 0]
    if negative_margins:
        first_negative = negative_margins[0]
        print(f"\nMargin turns negative at {first_negative['cost_bps']} bps "
              f"(margin = {first_negative['margin']*100:.1f}%)")
    else:
        print(f"\nMargin remains positive at all tested cost levels (highest: "
              f"{max(r['cost_bps'] for r in results)} bps).")

    # Verify 3 bps baseline.
    baseline = results[0]
    print(f"\n3 bps baseline (canonical):")
    print(f"  Momentum total return: {baseline['mom_total_return']*100:.1f}%")
    print(f"  (expected ~309.4% on 30-name universe; check against xsect.py output)")


if __name__ == '__main__':
    main()
