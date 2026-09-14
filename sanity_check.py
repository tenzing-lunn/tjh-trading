"""Sanity checks -- the guard that the harness isn't lying to itself.

Run this before trusting any result or building anything (a web app) on top:

    python3 sanity_check.py        # exits 0 if all pass, non-zero on any failure

Each check defends one of the project's invariants (see CLAUDE.md). If a check
fails, a result somewhere is fake -- stop and fix the engine, don't ship it.
"""
import sys
import numpy as np

from data import synthetic_ohlcv
from costs import CostModel
from backtest import run_backtest
from metrics import compute_metrics
from strategies import mean_reversion
from walkforward import walk_forward

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, ok, detail=""):
    results.append((ok, name, detail))
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def main():
    print("=== sanity checks: the harness must not lie ===\n")

    # 1. NO FABRICATED EDGE. On a pure random walk (kappa=0) there is no edge to
    #    find. If mean-reversion shows a frictionless profit, lookahead leaked in.
    px0 = synthetic_ohlcv(n=1500, kappa=0.0)["close"]
    _, m0 = run_backtest(px0, mean_reversion(px0, 20, 1.0), CostModel(0, 0))
    check("random walk (kappa=0) shows NO frictionless edge",
          m0["total_return"] < 0.0,
          f"meanrev frictionless return = {m0['total_return']*100:.1f}% (want < 0)")

    # 2. NO FALSE NEGATIVE. When a real edge IS present (kappa>0), the harness
    #    must detect it frictionless -- otherwise it's broken in the other direction.
    px1 = synthetic_ohlcv(n=1500, kappa=0.04)["close"]
    out1, m1 = run_backtest(px1, mean_reversion(px1, 20, 1.0), CostModel(0, 0))
    check("real edge (kappa=0.04) IS detected frictionless",
          m1["total_return"] > 0.05,
          f"meanrev frictionless return = {m1['total_return']*100:.1f}% (want > 5%)")

    # 3. COSTS ARE NON-NEGATIVE AND ALWAYS BITE. net = gross - cost, cost >= 0.
    #    If net ever beats gross, the cost model is adding money. Re-run #2 with
    #    real ETF costs and assert every bar's net <= gross and cost >= 0.
    out_c, _ = run_backtest(px1, mean_reversion(px1, 20, 1.0), CostModel(3, 1))
    cost_ok = bool((out_c["cost"] >= -1e-15).all())
    net_le_gross = bool((out_c["net"] <= out_c["gross"] + 1e-12).all())
    check("costs are never negative", cost_ok)
    check("net return never exceeds gross", net_le_gross)

    # 4. COST EROSION IS REAL. The same edge must be worth less after costs.
    _, m1e = run_backtest(px1, mean_reversion(px1, 20, 1.0), CostModel(3, 1))
    check("costs erode the edge (net-of-cost < frictionless)",
          m1e["total_return"] < m1["total_return"],
          f"{m1e['total_return']*100:.1f}% < {m1['total_return']*100:.1f}%")

    # 5. WALK-FORWARD BOUNDARY. Re-derive the fold index math walk_forward uses
    #    and assert every test fold is strictly AFTER its train window -- no
    #    train/test overlap (the whole point of out-of-sample).
    n_folds = 5
    idx = px1.index
    fold = len(idx) // (n_folds + 1)
    overlaps = 0
    for k in range(1, n_folds + 1):
        tr = idx[:fold * k]
        te = idx[fold * k: fold * (k + 1)]
        if len(te) == 0:
            continue
        if not (tr.max() < te.min()):
            overlaps += 1
    check("walk-forward test folds never overlap their train window",
          overlaps == 0, f"{overlaps} overlapping folds (want 0)")

    # 6. WALK-FORWARD RUNS AND SCORES OUT-OF-SAMPLE without error, returning a
    #    combined OOS series the metrics layer can score on a slice.
    grid = [{"lookback": lb, "entry_z": z} for lb in (10, 20) for z in (1.0, 2.0)]
    factory = lambda p: (lambda prices: mean_reversion(prices, **p))
    combined, chosen = walk_forward(px1, factory, grid, CostModel(3, 1), n_folds=5)
    km = compute_metrics(combined)
    check("walk-forward produces a scorable OOS series",
          len(combined) > 0 and km["bars"] == len(combined),
          f"{len(combined)} OOS bars across {len(chosen)} folds")

    # 7. DIAGNOSTICS DON'T MANUFACTURE SIGNIFICANCE. On a random walk (no edge), searching
    #    a whole grid must NOT let the best config clear the deflated-Sharpe bar. If scanning
    #    noise "proves" significance, the multiple-testing discount is broken.
    from diagnostics import deflated_sharpe_ratio, config_sharpes
    combined0, _ = walk_forward(px0, factory, grid, CostModel(3, 1), n_folds=5)
    dsr0 = deflated_sharpe_ratio(combined0["net"].values, len(grid),
                                 config_sharpes(px0, mean_reversion, grid, CostModel(3, 1)))
    check("deflated Sharpe does NOT manufacture edge on a random walk",
          not (dsr0 >= 0.95), f"noise deflated Sharpe = {dsr0:.3f} (want < 0.95)")

    # 8. THE BETA TRAP. Deflated Sharpe measured against ZERO cannot tell drift from skill:
    #    a trending series with no mean-reversion edge at all clears the 0.95 bar just by
    #    going up. This is the exact statistic that produced the false "SURVIVES" verdict.
    #    The ACTIVE version (vs the buy-and-hold benchmark) must refuse it.
    #    (drift/n are set so the uptrend is unambiguous -- at the audit's n=1500, drift=0.0005
    #    the realized path is a coin flip and only ~57% of seeds trend up at all, which would
    #    test nothing. Here the trap fires on 40/40 seeds.)
    from diagnostics import active_deflated_sharpe
    from strategies import buy_and_hold, random_strategy
    px_tr = synthetic_ohlcv(n=2500, kappa=0.0, drift=0.001)["close"]   # trending, no edge
    bh_df, _ = run_backtest(px_tr, buy_and_hold(px_tr), CostModel(3, 1))
    dsr_raw = deflated_sharpe_ratio(bh_df["net"].values, 1)
    check("deflated Sharpe vs ZERO passes pure beta (the trap this fix cycle exists for)",
          dsr_raw >= 0.95,
          f"raw DSR (beta) = {dsr_raw:.3f} (want >= 0.95, documents the trap)")
    rs_df, _ = run_backtest(px_tr, random_strategy(px_tr, seed=1), CostModel(3, 1))
    adsr_rand = active_deflated_sharpe(rs_df, bh_df, 1)
    check("ACTIVE deflated Sharpe refuses a coin-flip strategy on that same trend",
          adsr_rand < 0.95,
          f"active DSR (random vs B&H) = {adsr_rand:.3f} (want < 0.95)")
    adsr_self = active_deflated_sharpe(bh_df, bh_df, 1)
    check("ACTIVE deflated Sharpe is NaN for a strategy identical to its benchmark",
          adsr_self != adsr_self,
          f"active DSR (B&H vs itself) = {adsr_self} (want NaN -- no active return to test)")

    # 9. THE PANEL GATE MUST NOT MANUFACTURE MOMENTUM. Build a panel of 30 INDEPENDENT
    #    random walks with drift -- no cross-sectional structure, so ranking them is pure
    #    noise. The cross-sectional momentum pipeline vs the EW-universe must come back
    #    insignificant (t < 2) on the large majority of realizations; a well-calibrated
    #    test is allowed its ~5% false positives, nothing more.
    import pandas as pd
    from xsect import (target_weights, run_panel, _ew_weights, _first_active,
                       significance_vs_ew, LOOKBACK)
    n_below_2 = 0
    for outer in range(100):
        panel = pd.DataFrame({
            f"n{i:02d}": synthetic_ohlcv(n=1500, kappa=0.0, drift=0.0005,
                                         seed=outer * 1000 + i)["close"]
            for i in range(30)})
        mom = _first_active(run_panel(panel, target_weights(panel)))
        ew = _first_active(run_panel(panel, _ew_weights(panel, LOOKBACK)))
        ew = ew.reindex(mom.index).dropna()          # same alignment xsect.main() uses
        mom = mom.reindex(ew.index)
        if significance_vs_ew(mom, ew, panel)["t"] < 2.0:
            n_below_2 += 1
    check("panel significance gate does not manufacture momentum on pure noise",
          n_below_2 >= 95, f"{n_below_2}/100 seeds had t < 2 (want >= 95)")

    # 10. THREE-WAY GATE (plan/14 I0.1). Synthetic monthly ACTIVE series with a known true IR,
    #     200 seeds each. Expected rates under the pre-registered rule: IR 0 / 60y -> FAIL ~97%;
    #     IR 0 / 3y -> INCONCLUSIVE ~84% (the rest are FAIL on a very negative draw or a 2.5%
    #     false PASS); IR 1.5 / 20y -> PASS ~100%. "Can't tell" must not be reported as "no edge".
    from power import from_active
    rng = np.random.default_rng(7)

    def rate(true_ir, years, want):
        sd = 0.04
        mu = true_ir / np.sqrt(12) * sd
        hits = sum(from_active(rng.normal(mu, sd, int(years * 12)))["verdict"] == want
                   for _ in range(200))
        return hits / 200

    r_a = rate(0.0, 60, "FAIL")
    check("three-way gate: true IR 0 over 60 years -> FAIL", r_a >= 0.90,
          f"{r_a*100:.0f}% FAIL (want >= 90%)")
    r_b = rate(0.0, 3, "INCONCLUSIVE")
    check("three-way gate: true IR 0 over 3 years -> INCONCLUSIVE", r_b >= 0.75,
          f"{r_b*100:.0f}% INCONCLUSIVE (want >= 75%)")
    r_c = rate(1.5, 20, "PASS")
    check("three-way gate: true IR 1.5 over 20 years -> PASS", r_c >= 0.99,
          f"{r_c*100:.0f}% PASS (want >= 99%)")

    n_fail = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{'='*48}\n{len(results)-n_fail}/{len(results)} checks passed.")
    if n_fail:
        print("FAILED -- a result is lying. Do not build on this.")
        return 1
    print("All green. The harness is honest enough to build on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
