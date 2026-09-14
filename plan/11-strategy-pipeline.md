# 11 — Strategy Pipeline (how we find, test, run, and show strategies)

Home: [[PROJECT_PLAN]] · Charter: [[plan/07-charter-what-we-do]] · Status: [[plan/09-status-where-we-are]]
Specs it depends on: [[plan/10-verdict-and-diagnostics-spec]] · [[webapp/DESIGN_TARGET]] (mockup: `webapp/MOCKUP.html`)

*The definitive answer to "what exactly are we doing, how are strategies tested, how are they
run, and what does the web app show." This reconciles the wide "4-prompt" scan with our
skeptic's harness. The `.py` engine stays canonical for math; this file is canonical for the
pipeline design. For Claude CLI: build to this doc + plan/10 + DESIGN_TARGET.*

---

## 0. The core philosophy (resolves the tension)
Two instincts were in conflict in the plan: **"generate wide, filter hard"** (the 4-prompt
video) vs **"test few, well-reasoned ideas"** (our charter). They are not opposites if you
**sequence** them:

> **Scan wide to DISCOVER candidates. Demand a high bar to BELIEVE one.**

A wide scan is allowed to *find* things. Nothing is *believed, funded, or paper-traded* until it
clears all four gates in §3. The wide scan produces suspects; the gates produce verdicts. This
keeps the breadth of the 4-prompt approach without inheriting its self-deception.

## 1. What we trade (scope)
Liquid US equities & ETFs first (SPY/QQQ/IWM + a handful of liquid large caps), **split/dividend
adjusted**, daily bars, swing-style holding (days–weeks). Options stay paper-only; intraday is a
researched phase-2. Universe is Tenzing's call (liquidity in, junk out). See [[plan/07-charter-what-we-do]].

## 2. What a "strategy" is (and the curated library)
A strategy is a function `(prices, **params) -> position Series in [-1, 1]`, same contract as
everything in `strategies.py`. The library is **curated, not sprawling**:
- **Keep** economically distinct families: buy&hold + random (baselines), mean-reversion
  (z-score), trend (SMA crossover), **cross-sectional momentum** (the best 4-prompt idea —
  rank a universe, long top / flat-or-light-short bottom), and `kronos_signal`.
- **Reject** false diversity: Ichimoku / Vortex / TRIX / KAMA etc. are the same trend idea in
  different clothes. Twelve correlated trend variants is not twelve strategies; it's one
  strategy and eleven extra chances to fool ourselves.
- New families enter the library only with a written thesis ([[research/_thesis-template]]).

## 3. How a strategy is TESTED — the four gates (in order)
Every candidate, whether hand-written or found by a wide scan, runs this gauntlet. The engine
computes all of it; nothing is reimplemented elsewhere.

**Gate 1 — Net of realistic costs.** Score under `costs.py` regimes (frictionless = diagnosis
only; **liquid ETF 3/1 bps = the truth for equities**; cheap-option 300/50 bps for options).
The 1 bp/side the video used is banned — it manufactures fake edge.

**Gate 2 — Out-of-sample walk-forward.** Params are chosen on TRAIN only and scored on unseen
TEST (`walkforward.py`, already correct — do NOT replace it with the video's stitched-OOS
version, which can't even build an IS-vs-OOS scatter). Must beat **both** buy-and-hold AND
random, OOS, net of costs.

**Gate 3 — Multiple-testing discount.** The more configs/strategies scanned, the more a top
result is luck. Report **deflated Sharpe** (Bailey–López de Prado) or at minimum the trial
count `N` next to every Sharpe. "Best of 9,000" is not the same as "good." (Spec: [[plan/10-verdict-and-diagnostics-spec]] Part B.)

**Gate 4 — Robustness / economic story.** Diagnostics (`diagnostics.py`): per-year & per-fold
consistency, trade count (flag <30/fold), regime split (up/down/chop). If the edge is one year
or one regime, it's suspect. AND Tenzing must supply *why the edge exists and who's on the
other side* before we believe it. A green number with no economic story is treated as luck.

Only a candidate that clears **all four** is a "survivor."

## 4. How a strategy is RUN (the lifecycle)
```
 idea ─▶ implement signal ─▶ harness gauntlet (§3) ─▶ verdict auto-logged ─▶ Tenzing judgment
   │                                                          │
   │                                            DEAD ◀────────┤ (the base rate — most die here)
   │                                                          ▼
   └──────────────────────────  SURVIVOR ─▶ paper-trade on Alpaca (weeks) ─▶ trade journal
                                                              │
                                       real money? = separate deferred decision, never automatic
```
- **Research runs** happen in the terminal: `run.py <ticker.csv>` (and the web app's on-demand
  API). Every real run auto-appends a verdict row (`verdicts.jsonl`, see plan/10) — Tenzing adds
  the *judgment*, not the typing.
- **Wide scan** — **BUILT (`scan.py`).** Loops the curated library × param grids × the universe
  through the SAME harness, scores buy&hold + random through the identical folds (Gate 2), prints
  the trial count `N` next to every Sharpe (Gate 3 minimum) and flags <30 trades/fold (Gate 4).
  Ranks OOS-net-of-costs; a result earns `EDGE?` only if it beats both baselines AND is positive
  AND non-thin, else `suspect`/`dead`. It does NOT reimplement costs/backtest/walkforward. Each
  ticker is scored independently, so it needs no multi-asset engine (that is cross-sectional
  momentum's job, still deferred). If `realdata/spy.csv` is present it also judges every result
  **vs holding SPY over the same OOS window** (the charter's canonical opportunity-cost bar).
  Expanded via `fetch_universe.py` to **53 liquid names** (index ETFs + ~40 large caps): **0 EDGE?,
  12 suspect, 94 dead** across 106 backtests — the honest base rate (simple timing rules do not beat
  holding the index on liquid daily bars). `EDGE?` also requires a **deflated Sharpe ≥0.95**
  (Gate 3, `diagnostics.py`), and each top name gets auto **red flags** ("92% of return from 2020",
  "only 1 trade/fold") so a beginner SEES why a big number is fake. Compute **~40 ms/backtest, ~4s
  total**; scaling to hundreds of names costs seconds and $0.
- **Promotion** to paper requires a human sign-off (Tenzing's story + judgment, audited by
  Fable), not just a green cell.

## 5. What we ADOPT vs REJECT from the 4-prompt pipeline
| From the video | Verdict | Why |
|---|---|---|
| Wide universe (L1, ~30 assets/15yr) | **Adopt** | Breadth is good — feed it through our harness. |
| Cross-sectional momentum (L4) | **Adopt (long-only first)** | Genuinely distinct signal; shorting bottom-third may be untradeable in a $3–5k account. |
| IS-vs-OOS scatter idea | **Adopt** | Good visualization — built on our REAL walk-forward, not the video's. |
| 1 bp/side cost | **Reject** | Fantasy-cheap; contradicts our 3 bp floor. The biggest single danger. |
| Their "walk-forward" (discard IS, score stitched OOS) | **Reject** | Doesn't tune-then-test; moves selection bias to reporting. Reuse `walkforward.py`. |
| Reshuffle bootstrap | **Reject** | Sharpe is permutation-invariant → bands collapse. Use resample-with-replacement / block bootstrap. |
| ~50 strategy families | **Reject most** | Correlated trend variants = false diversity; impossible to keep bug-free. |
| No multiple-testing correction | **Reject** | Add deflated Sharpe / trial count (Gate 3). |

## 6. What the WEB APP shows (the pipeline, made visible)
The app is the *interpretation layer* — it displays what Python computed, never recomputes.
Target look = `webapp/MOCKUP.html`; panel spec = [[webapp/DESIGN_TARGET]]. Five panels:
1. **Price + signal overlay** (long/flat/short shading + trade markers).
2. **Pay-per-trade simulator** — equity net of costs vs buy-and-hold vs SPY (the lesson).
3. **Cost sliders** — drag spread/slippage/fee → harness recomputes live.
4. **Verdict panel** — REAL/DEAD + OOS-net-of-costs, Sharpe, max DD, trades vs benchmark.
5. **Robustness / red-flag panel** — per-year bars + auto red-flags ("82% of return from 2020",
   "only 11 trades/fold", "best of 12 configs — deflated Sharpe ~0.2") so a non-expert
   SEES why a result might be fake. Flags guide; the advance/kill call stays human.

**Wide-scan view — BUILT (2026-07-06): the Engine Room (`/engine`).** `scan.py` and `xsect.py`
now run **live** in the browser via `engine_api.py` + new `api_server.py` routes
(`/api/universe`, `/api/engine/scan`, `/api/engine/momentum`, `/api/alpaca/status`): a data
panel showing per-ticker provenance (Alpaca / yfinance-fallback / cache), the full ticker ×
strategy table where every row expands into its gate-by-gate pass/fail checklist + red flags,
the Thesis 001 panel (baselines, per-year bars, regime split, sensitivity sweep, PSR), and the
live Alpaca paper account. Same hard rule — zero math in JS, the engines are called unmodified.

*Still future (Phase B/C, deferred): the IS-vs-OOS scatter (each dot a backtest) and Supabase
recording live option chains daily for honest options backtests.*

## 7. Hard invariants (do not break — for Claude CLI especially)
- The Python engine is the single source of truth. The scan wrapper, the app, and the logger all
  CALL `costs.py`/`backtest.py`/`walkforward.py`/`metrics.py` — none reimplement them.
- No-lookahead stays in the engine (`pos.shift(1)`), never in a strategy.
- No backtest math in JavaScript. Need a number in the app? Add it to the Python payload.
- Every believed result is net of costs, OOS, and discounted for the number of trials.
- No order execution / real money in any code path. Paper only, by hand for promotion.
