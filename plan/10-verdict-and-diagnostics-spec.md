# 10 — Build Spec: Verdict Auto-Logger + Robustness Diagnostics

Home: [[PROJECT_PLAN]] · Status: [[plan/09-status-where-we-are]] · For: Claude Code to implement

*Two related Python jobs. Both keep the invariant: the engine computes truth, everything else
reads it. No new numbers in JavaScript. Hand this file to Claude Code as the spec.*

---

## Part A — Verdict auto-logger
**Goal:** stop a human retyping verdicts. The harness writes each result to a machine-readable
log automatically; the human verdict log is rendered from it.

**Implement:**
1. Add `verdict_log.py` with `append_verdict(record: dict, path="verdicts.jsonl")` that appends
   one JSON line. Record fields: `timestamp`, `ticker`, `strategy`, `params`, `cost_regime`
   (spread/slippage bps), `oos_total_return`, `oos_sharpe`, `oos_max_dd`, `num_trades`,
   `buy_hold_return`, `spy_return` (benchmark over same window), `beats_bh` (bool), plus the
   diagnostics from Part B.
2. In `run.py`, after the walk-forward block, build that record from the existing `metrics`
   dict and call `append_verdict`. One line per real run. (Skip synthetic runs, or tag them
   `synthetic=true` so they never pollute the real track record.)
3. Add `render_verdict_log.py` (or a `run.py --render-log` flag) that reads `verdicts.jsonl`
   and regenerates `plan/02-verdict-log.md` as a readable table, newest first. Tenzing edits only
   the **judgment** column (real/luck/kill) in a sidecar, never the auto rows.
4. Gitignore `verdicts.jsonl` if it embeds vendor returns; otherwise keep it (it's just metrics).

**Don't:** don't let the logger recompute anything — it only records what `metrics.py` produced.

## Part B — Robustness diagnostics (so a non-expert can SEE "it only worked in 2020")
**Goal:** surface *why* a result might be fake, as numbers a beginner can read, and auto-raise
red flags. This is what makes Tenzing's judgment role possible. Flags GUIDE; they don't decide.

**Status: BUILT — `diagnostics.py`.** Deflated Sharpe (Bailey–López de Prado), per-year
return+Sharpe, trades/fold, SPY-regime split, and `red_flags()` are implemented and wired into
`scan.py` as the Gate-3 filter (`EDGE?` requires deflated Sharpe ≥0.95); a `sanity_check.py`
guard asserts noise can't manufacture significance. **Part A: BUILT 2026-07-02 — `verdict_log.py`.**
Every real `run.py` walk-forward appends to `verdicts.jsonl` (synthetic runs tagged and
excluded); `python3 verdict_log.py --write-md plan/02-verdict-log.md` renders the AUTO
section. The Judgment column stays human.

**Implement in a new `diagnostics.py`, computed from the walk-forward output:**
1. **Per-year (and per-fold) return + Sharpe.** A small table/series. If all the edge comes
   from one year, that's the tell. Return as a list the web app can bar-chart.
2. **Trade count + an EV-per-trade with its standard error.** Low trade count = Sharpe inflated
   by luck. Flag if `num_trades < 30` per fold.
3. **Deflated / multiple-testing-aware Sharpe.** Given how many configs were tried (param grid
   size), discount the best Sharpe. Implement Bailey–López de Prado deflated Sharpe (or, minimum
   viable: report the trial count `N` next to the Sharpe so the discount is visible).
4. **Regime split.** Performance in up-trend vs down-trend vs chop (simple SPY-based regime tag).
   If it only works in one regime, flag it.

**Red-flag function:** `red_flags(metrics, diagnostics) -> list[str]` returning human strings like
`"Only 11 trades/fold — Sharpe may be luck"`, `"82% of return came from 2020"`,
`"Best of 12 configs — deflated Sharpe ~0.2"`. These strings feed both the verdict record
(Part A) and the web app's red-flag panel.

## Web app hook (panel ⑤ — see webapp/DESIGN_TARGET.md)
Render the per-year bars + the red-flag list in the verdict area, so Tenzing literally sees the
weakness. **The automated flag is a prompt to look closer, not a verdict.** The advance/kill
call stays human — the app just makes sure a beginner is looking at the right thing.
