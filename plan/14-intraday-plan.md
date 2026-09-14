# 14 — Short-Term Trading: intraday + swing, on simulated 15-minute-delayed data

Home: [[PROJECT_PLAN]] · Previous plan: [[plan/12-real-markets-plan]] · Charter: [[plan/07-charter-what-we-do]]

*Written 2026-09-14. Two inputs: (1) Phase 1 of plan/12 ended with momentum UNPROVEN, and the
power analysis showed that a monthly strategy on 7–17 years of data cannot reach t ≥ 2 even if
the edge is real (see "Why this plan exists"); (2) Tenzing's "Integrated Quant Framework"
document (OpenBB + QUANTAXIS + point-in-time data + risk engine), from which we adopt the
practices worth adopting and skip the rest. Model roster and ground rules are unchanged from
plan/12. **Humans still own every gate. No agent places an order.***

---

## Why this plan exists

| Fact | Consequence |
|---|---|
| Momentum's honest t-stat is 1.14–1.78; the gate needs ≥ 2 | Not rejected: **undetectable** with 12 bets/yr. 27–149 yrs needed for 80% power |
| A strategy making ~daily independent bets gathers evidence 20× faster | Short horizons are the only way to reach a verdict on the data we have |
| Charter already says "swing-style, daily bars, hold days–weeks" | Swing is a return to charter; **intraday is a scope change** (reverses the 2026-07-02 "park Kronos" decision) |
| Alpaca's free plan gives full SIP minute bars for any US stock since 2016-01, adjusted, 200 req/min (verified 2026-09-14 with our keys) | Intraday research costs $0. Only the **last 15 minutes** are locked |
| Real-time SIP is ~$99/mo | **Deferred.** We simulate the 15-minute delay inside the engine and only revisit once a strategy survives it |

**Standing decision (2026-09-14):** scope is now **intraday + swing (minutes → ~2 weeks)**.
Anything held longer than a month goes back to the plan/12 track. Every intraday strategy is
tested *with the 15-minute delay baked in*: a signal computed at minute *t* can act no earlier
than *t + 15*. If it can't survive that, we don't buy the feed.

---

## What we take from the Integrated Quant Framework document (and what we don't)

| IQF idea | Verdict | Where it lands |
|---|---|---|
| Fail-closed data-quality gate (stale, gaps, absurd returns block the run) | **Adopt.** Would have caught the WRK single-bar bug | I1.2 |
| Point-in-time timestamps: `observation_time` vs `announcement_time` vs `effective_time` | **Adopt** the schema now (cheap); populate it when fundamentals/earnings enter a thesis | I1.1 |
| Immutable experiment ledger (every trial counted, so deflated Sharpe is honest) | **Adopt** | I1.5 |
| Stress tests we lack: stale-data delay, bootstrap, capacity, correlation with existing strategies | **Adopt.** The delay test *is* our 15-minute simulation | I2.4 |
| Backtest → replay → shadow → paper → small live ladder | **Adopt** | Phase 4 |
| Risk engine + kill switch outside the strategy process; broker reconciliation | **Adopt** | I4.3, I4.4 |
| AI research layer that can eventually execute on its own | **Adopt as the end goal**, gated: AI may propose/backtest/shadow; live authority is granted by a written policy and the AI can never disable its own risk checks | I4.5 |
| Parquet + DuckDB storage | **Adopt** for minute data (30 names × 1M bars won't fit CSV workflows) | I1.1 |
| Regime engine, cross-asset confirmation | **Later.** Only as a pre-registered thesis, never as a post-hoc filter (plan/12 P3.4 rule) | — |
| 7-family signal fusion with learned weights | **Reject.** It's the multiple-testing trap with extra steps; against charter | — |
| QUANTAXIS as backtest/account engine | **Reject for now.** Our engine is audited and 40 ms/backtest; re-auditing a Chinese-market-first framework buys nothing until live execution | Revisit at Phase 4 if our own OMS gets painful |
| OpenBB as data layer | **Later.** Not needed for prices (Alpaca is better); reconsider when a thesis needs point-in-time fundamentals |
| Kafka / Prometheus / Kubernetes / MLflow | **Skip.** Wrong scale. A cron job, a JSONL log and a web-app panel do the same job for one person running agents |

---

## Phase 0 — Fix the verdict rule before testing anything new

| # | Task | Done when | Model | Why this model | Depends on |
|---|---|---|---|---|---|
| I0.1 ✅ `2761a70` | **Three-way gate** (`power.py`, pre-registered, `IR_MIN = 0.5` annual IR of the active return). **PASS**: t ≥ 2 (plus the existing beats-EW/random/SPY and no-red-flag gates). **FAIL**: the edge is ruled out, i.e. the 95% CI upper bound `IR_hat + 1.96/√T` < `IR_MIN`. **INCONCLUSIVE**: everything else. Power P(t ≥ 2 \| IR = IR_MIN) and years-for-80%-power are always reported. Result: momentum is INCONCLUSIVE on the 30-name core (t 0.34, power 25%) and the point-in-time panel (t 1.17/1.26, power 54%) | `xsect.py` prints power + the three-way verdict; `plan/12` Gate G1 and `plan/02-verdict-log` restated; a unit test shows a low-power series → INCONCLUSIVE, a zero-edge high-power series → FAIL | **Opus 5** | Statistics in the core verdict path | — |
| I0.2 | **Frequency-agnostic engine.** `ppy=252` is hard-coded in `metrics.py`, `walkforward.py`, `diagnostics.py`, `backtest.py`, `export_results.py`. Make it a property of the price series (inferred from median bar spacing, as `forecast_kronos.py` already does) and thread it through | All existing daily results reproduce exactly; a 1-minute synthetic series annualises with ppy ≈ 98,280 (390 × 252) | **Opus 5** | Touches every core file; must not change daily numbers | — ⇉ |
| I0.3 | **Retire the 30-trades/fold rule as a hard flag.** `scan.py:53` marks slow strategies "suspect" for being slow. Replace with the I0.1 power check (trades/fold stays as a display column) | Rerun `scan.py`; the 0-EDGE headline holds; no row is suspect *only* because of trade count | **Sonnet 5** | Clear spec, existing code | I0.1 |

---

## Phase 1 — Data foundation (the IQF part)

| # | Task | Done when | Model | Why this model | Depends on |
|---|---|---|---|---|---|
| I1.1 | **`fetch_intraday.py`.** Alpaca SIP 1-minute bars, 2016-01 → now, `adjustment=ALL`, for SPY + QQQ + the 30-name core (`fetch_universe.SECTORS`), into `intraday/<sym>.parquet` (gitignored) with a manifest carrying `retrieval_time`, `source`, `feed`, `adjustment`, first/last bar, row count. Resumable; 10k-bar pages; stays under 200 req/min. Add `duckdb` + `pyarrow` to requirements | All 32 symbols fetched; SPY 2016-01-04 shows 825 bars (matches the 2026-09-14 probe); manifest complete; a DuckDB query over all files runs | **Sonnet 5** | Clearly specified downloader with a known API; Haiku would be fine but the paging/rate logic needs care | I0.2 ⇉ |
| I1.2 | **Fail-closed data-quality gate.** `dq.py`: per symbol, refuse a file that has (a) a session with < 60% of expected bars, (b) any \|1-min return\| > 20% not on a known split date, (c) a first bar after the vendor's stated start, (d) a gap > 3 trading days inside the range. Bad symbols are *excluded with a reason*, never imputed. Apply the same checks to `realdata/` daily files (closes the plan/12 P1.4 fix list items 1, 3, 4) | `python3 dq.py` prints a per-symbol PASS/EXCLUDE table; a synthetic WRK-style single-bar file is EXCLUDED; the engine refuses to load an unchecked file | **Opus 5** | This is the bug class that bit us in P1.4; a soft check is worse than none | I1.1 |
| I1.3 | **Switch the daily fetch to SIP.** `engine_api.py:104` / `fetch_alpaca.py` use the IEX feed (~2.5% of volume) for *daily* bars. Historical SIP is allowed on the free plan; use it and re-fetch `realdata/` | Daily closes/volumes differ slightly from the IEX versions; `scan.py` and `xsect.py` rerun; the 0-EDGE / UNPROVEN headlines hold (if they don't, stop and report) | **Haiku 4.5** | One-line feed change plus a rerun | — ⇉ |
| I1.4 | **Measure real spreads.** `spreads.py`: pull Alpaca historical NBBO quotes (free) for each name, sample ~20 days per year 2016→now, and compute the quoted half-spread in bps by symbol × time-of-day bucket (open 9:30–10:00, mid, close 15:30–16:00). Output `research_data/spreads.csv` + a table in `Costs.md` | Table exists; SPY mid-day half-spread lands in the ~0.5–1.5 bps range (sanity); single names show the open > mid > close pattern | **Sonnet 5** | Data pull + aggregation; the *interpretation* is Tenzing's | I1.1 ⇉ |
| I1.5 | **Intraday cost regime.** New `CostModel` regime `INTRADAY` in `costs.py`: half-spread from I1.4 by symbol × time bucket, plus slippage = f(order size / bar volume) with a stated conservative constant, plus the SEC/FINRA sell-side fees. Keep `LIQUID_ETF` unchanged for daily work | `costs.py` prints the new regime table; a full round-trip of SPY at the open costs more than at mid-day; **Tenzing signs the constants** | **Opus 5** | `costs.py` is "the most important file"; a flattering intraday cost model would invalidate everything downstream | I1.4 |
| I1.6 | **Experiment ledger.** `experiments.jsonl`: every backtest/scan/sweep appends {id, git sha, data manifest hash, strategy, params, window, result, who/what launched it}. Append-only; `diagnostics.deflated_sharpe_ratio` reads its trial count *from the ledger*, not from a caller-supplied `n_trials` | Running `scan.py` twice appends 2 × N rows; DSR reported with the ledger count; a test proves a caller can't under-report N | **Sonnet 5** | Logging plumbing with one invariant to enforce | I0.2 |
| I1.7 | **Independent data cross-check (one-off).** Databento's $125 signup credit covers a few symbol-months of `ohlcv-1m`. Pull SPY + 3 names for 2 stressed months (Mar 2020, Aug 2024) and diff against Alpaca bar-by-bar | A short note in `research/audits/intraday-data.md`: % of bars matching within 1 tick; any systematic gap explained. **Proposal only if it would cost money beyond the credit** | **Haiku 4.5** | Mechanical diff; the credit is free but Tenzing creates the account, not the agent | I1.1 |

---

## Phase 2 — Engine adaptation for intraday

| # | Task | Done when | Model | Why this model | Depends on |
|---|---|---|---|---|---|
| I2.1 | **Sessions and gaps.** `backtest.py` must know where a trading day ends: no position may be "earned" across the overnight gap unless the strategy explicitly holds overnight; the overnight return is attributed to a separate `overnight` leg so intraday-only and swing strategies are scored on what they actually held | A synthetic 2-day series with a 5% overnight gap: an intraday-only strategy shows 0 exposure to it; a hold-overnight strategy shows 100% | **Opus 5** | Core engine; the no-lookahead invariant now has a second axis (time-of-day) | I0.2 |
| I2.2 | **The 15-minute delay, in the engine.** `held = positions.shift(k)` where `k` = delay in bars (15 for 1-min, 3 for 5-min, 1 for daily). Default for intraday = 15. The delay is a *cost-regime-level* setting so nobody can forget it | Same strategy run with delay 1 vs 15 shows the difference; a test asserts intraday runs refuse delay < 15 unless `--realtime-feed` is set (which is refused until a paid-feed decision is logged) | **Opus 5** | This is the rule that decides whether we ever pay $99/mo; it must be unbypassable | I2.1 |
| I2.3 | **Walk-forward on intraday folds.** Folds by calendar (e.g. 6-month train / 2-month test, rolling), parameters picked on train only; baselines (buy-and-hold, random-with-matched-holding-period, SPY same window) scored through the same folds | `walkforward.py` runs on SPY 1-min 2016→now in < 2 min; random baseline percentile reported | **Opus 5** | Fold logic + selection boundary | I2.2 |
| I2.4 | **New stress tests** (from IQF §13): extra stale-data delay (30/60 min), bootstrap CI on the active return, capacity (P&L vs order size / bar volume), correlation of the new strategy's returns with Thesis 001's | `diagnostics.py` reports all four; each has a synthetic test showing it catches what it's meant to | **Opus 5** | Statistics in the verdict path | I2.3 |
| I2.5 | **Sanity checks for the intraday engine.** Random-walk minute data → no strategy passes; a planted intraday mean-reversion → detected at delay 1, and the test *documents* how much of it the 15-minute delay eats | `sanity_check.py` gains checks #10–#12, all pass | **Opus 5** | Proves the engine can't hallucinate an intraday edge | I2.4 |
| I2.6 | **Audit Phase 1 + 2.** Lookahead across the session boundary, delay bypasses, cost model optimism, data-quality gaps | `research/audits/intraday-engine.md`, each item confirmed / wrong / unclear | **Fable 5.1** | Adversarial audit; the model that built it doesn't grade it | I1.5, I2.5 |

---

## Phase 3 — First short-term theses (pre-registered, few)

Tenzing writes each thesis using `research/_thesis-template.md` **before** anyone looks at
results. Each states: the economic reason, the horizon, the exact rule, the minimum edge it
must show (for the I0.1 power check), and what would kill it. Candidates, not commitments:

| # | Thesis candidate | Horizon | Why it might exist | Model that runs it |
|---|---|---|---|---|
| I3.1 | Overnight vs intraday return split (SPY/QQQ): hold close→open only | 1 night | Well-documented; most index return accrues overnight. Cheap to test; a clean first calibration of the whole pipeline | **Sonnet 5** |
| I3.2 | Short-term reversal, 1–5 day, on the 30 names | days | Liquidity provision; the academic sibling of momentum at the opposite horizon | **Sonnet 5** |
| I3.3 | Intraday mean reversion on SPY after the opening 30 min | hours | Opening imbalance; **must** survive the 15-min delay, which is the whole question | **Sonnet 5** |
| I3.4 | Kronos zero-shot on 5-min bars (un-park the 2026-07-02 decision) | hours | Kronos is intraday-strongest; `forecast_kronos.py` already works on any bar spacing | **Sonnet 5** (run) |
| I3.5 | **Red-team the theses.** Was anything chosen after looking? Is the delay honoured? Does the ledger count every trial? | `research/audits/phase3-intraday.md` | **Fable 5.1** |

### 🚦 Gate G2 — Humans decide (Tenzing), three-way

Per thesis: **PASS** (survives OOS, net of the I1.5 regime, with the 15-min delay, t ≥ 2 and
power ≥ 50%), **FAIL** (a meaningful edge is ruled out), or **INCONCLUSIVE** (can't tell,
say why and what data would settle it). Only PASS proceeds. The realtime-feed purchase is
proposed **only** for a PASS whose edge the delay visibly erodes — with the 20× justification
written out.

---

## Phase 4 — Simulation → shadow → paper (the ladder), and the AI's authority

| # | Task | Done when | Model | Why this model | Depends on |
|---|---|---|---|---|---|
| I4.1 | **Event replay.** Feed a historical day bar-by-bar through the *live* signal code path with the 15-min delay; results must match the backtest for the same day | `replay.py` over 20 random days: identical positions to `backtest.py` | **Opus 5** | Backtest/live unification; divergence here is a lookahead bug | G2 |
| I4.2 | **Shadow mode.** Live (15-min-delayed SIP) signals logged, **no orders**, for ≥ 2 weeks; compare with expected | `shadow.jsonl` + a panel: expected vs observed signal, data staleness, gaps | **Sonnet 5** | Ops + logging | I4.1 |
| I4.3 | **Risk gate + kill switch, outside the strategy.** Separate process/file: max daily loss, max position, max orders/hour, data-staleness limit, broker-state mismatch → halt. Strategy code cannot import or modify it | Tests: each limit halts; a halted state persists across restarts until a human clears it | **Opus 5** | Safety-critical | I4.2 |
| I4.4 | **Paper trading + reconciliation.** Alpaca paper orders (fractional), idempotent client order IDs, continuous position/cash reconciliation, trade journal with modeled-vs-realised cost | ≥ 2 weeks of paper fills; journal cost gaps feed back into I1.5 (**Tenzing signs**) | **Opus 5** | Money-adjacent | I4.3 |
| I4.5 | **AI authority ladder (the end goal, written down).** Level 0: propose theses. Level 1: run backtests + ledger. Level 2: shadow. Level 3: paper, within I4.3 limits. Level 4: small live, only under a signed human policy with caps. Every decision logged with prompt, data hash, code sha, result. **The AI can never change I4.3 or its own level.** | `plan/15-ai-authority.md` drafted; **Tenzing signs**; the current level is stored in a file the AI has no write access to | **Fable 5.1** drafts, humans sign | Policy reasoning; the constraint set has to be airtight | I4.3 |
| I4.6 | **Safety audit of Phase 4.** Live-endpoint reachability, double-submit, stale-data trading, kill-switch bypass, AI privilege escalation | `research/audits/phase4-intraday.md`, all issues closed | **Fable 5.1** | High-stakes review | I4.5 |

---

## Order of work

```
I0.1 ─┬─ I0.3
I0.2 ─┼─ I1.1 ─┬─ I1.2 ─────────────────┐
      │        ├─ I1.4 ── I1.5 ─────────┼─ I2.1 → I2.2 → I2.3 → I2.4 → I2.5 → I2.6 (audit)
      │        └─ I1.7                  │                                        │
      └─ I1.6 ──────────────────────────┘                                   Phase 3 → G2 → Phase 4
I1.3 (independent, any time)
```

**First batch (parallel, each in its own worktree):** I0.1, I0.2, I1.3. Then I1.1 + I1.6 +
I0.3. Everything in Phases 0–2 is $0 and touches no orders.

**Decision points where Claude stops and asks Tenzing:** any paid dependency (I1.7 beyond the
credit; the realtime feed at G2); any rerun in I1.3 that changes an existing verdict; Tenzing's
sign-offs (I1.5, I4.4); every gate.
