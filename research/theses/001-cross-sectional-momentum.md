# Strategy Thesis 001 — Cross-Sectional 12-1 Momentum

Home: [[PROJECT_PLAN]] · Author: drafted by Tenzing/Claude from the engine spec, **pending
Tenzing's signature** · Status: **UNPROVEN — the edge over EW-universe is not statistically
distinguishable from luck (t=0.34); see the 2026-09-14 gate correction below**

*This is the thesis document the process ([[roles/ROLE_Tenzing]], [[roles/standup-template]])
calls for. It was written up AFTER the engine (`xsect.py`) was already built and run — see
[[plan/01-decision-log]] 2026-07-03 "Thesis 001 engine mismatch resolved" for why the
sequencing was pragmatic (we needed the panel engine to exist before anyone could test the
idea at all). Tenzing: read this, then either sign it as-is, amend the economic story, or
reject the result. The signature is the missing step — see [[plan/09-status-where-we-are]].*

---

**The claim:** Stocks that have outperformed over the trailing 12 months (excluding the most
recent month) continue to outperform over the next month. Rank a universe of liquid US stocks
by 12-1 trailing momentum every month-end; hold the top 10, equal-weight, long-only.

**Why it exists:** Investor underreaction / slow information diffusion (Jegadeesh & Titman,
1993). News about a company's improving fundamentals gets priced in gradually, not instantly —
analysts revise estimates slowly, institutions build positions over weeks not seconds, and
retail attention is slow to catch a trend. The people "on the other side" of this trade are
investors who sell winners too early (disposition effect / profit-taking) and anchor on stale
valuations, plus anyone indifferent to the momentum factor (index-huggers, value investors who
actively fade recent winners).

**Why it should persist:** Momentum is one of the most heavily documented anomalies in finance
and has NOT been fully arbitraged away, likely because (a) it's capacity-constrained and
crash-prone (large funds avoid overweighting it after 2009's momentum crash), (b) it requires
real turnover and trading costs that erode it for anyone not careful about execution, and
(c) behavioral biases that cause it are persistent, not a temporary information gap. That said
— "it's a famous anomaly" is not proof it works *for us*, which is exactly why it still has to
clear the same bar as everything else below.

**How to test it:** `xsect.py` — a purpose-built cross-sectional panel engine (single-name
`backtest.py` can't score a multi-asset rotation). Spec, locked before looking at sensitivity
neighbors:
- Universe: ~97 liquid US stocks (index ETFs excluded — see `EXCLUDE` in `xsect.py`), Tenzing's
  liquidity call via `fetch_universe.py`.
- Signal: 12-month trailing return, skipping the most recent month (252 trading days back,
  21-day skip) — the canonical academic spec.
- Rebalance: monthly, at month-end.
- Portfolio: top 10 names, equal weight, long-only (no short leg — shorting the bottom decile
  is likely untradeable in a $3–5k account; see [[plan/11-strategy-pipeline]] §5).
- Costs: liquid-ETF regime (3/1 bps) on full portfolio turnover — the honest regime, not the
  frictionless lie.
- No-lookahead: weights decided at month-end `t` are held from `t+1` (`weights.shift(1)`),
  the same convention as the single-name engine.
- `n_trials = 1` — canonical spec only, no grid search. A searched thesis is a weaker claim;
  we do not pick the best lookback/top-N after the fact (see the sensitivity sweep below,
  which is reported as robustness, never as selection).

**What would kill it:** Failing to beat **equal-weighting the same universe** (that would mean
the "selection" is really just survivorship — the universe itself, not stock-picking, is doing
the work) — this is the bar that matters most, more than beating SPY. Also: failing to beat
random top-10 picks, a **monthly active t-stat vs EW below 2** (see the 2026-09-14 correction
below — a probabilistic Sharpe below 0.95 was the original criterion here, but that statistic
turned out to be unfalsifiable for any long-only basket in a rising market: it can't tell
selection skill from just owning stocks), or a one-year-wonder pattern (>60% of the *edge over
EW*, not the raw return, from a single year).

**My prediction (pre-registered):** *[Tenzing — this line is intentionally unfilled. The run
below already happened (see the engine-mismatch note above), so the "prediction" here is
really an ex-ante economic judgment read against the result, not a blind guess. Write
honestly whether you'd have expected this before seeing the numbers, and what you think the
result is really measuring.]*

---
## Result (run 2026-07-03, updated 2026-07-05 with a broadened universe + robustness gauntlet)

**Window:** 2019-08-01 → 2026-07-02 (~7 years), ~97 stocks, monthly rebalance.

| Portfolio | Total return | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| **Momentum top-10** | **+972%** | 41.0% | 1.21 | −37.9% |
| EW universe (all names) | +265% | 20.6% | 1.01 | −33.7% |
| Hold SPY | +180% | 16.1% | 0.85 | −33.7% |

**The bar that matters:**
- Beats EW universe: **YES** (selection skill beyond just owning these names)
- Beats random top-10 picks: **YES**
- Beats holding SPY: **YES**

**Per-year, momentum vs EW universe** (won 5 of 8 years by raw-return *sign* — since shown to
be the wrong question, see the 2026-09-14 correction below; this table is kept as the
original, non-reproducible ~97-name run's historical record):
| Year | Momentum | EW universe |
|---|---:|---:|
| 2019 | +7.7% | +13.4% |
| 2020 | +157.4% | +36.9% |
| 2021 | +5.9% | +31.0% |
| 2022 | **−2.4%** | **−13.4%** (the drawdown year — momentum held up much better) |
| 2023 | +32.3% | +28.5% |
| 2024 | +32.3% | +16.8% |
| 2025 | +19.8% | +22.1% |
| 2026 (partial) | +78.3% | +12.9% |

**Robustness gauntlet (`xsect.py` + `diagnostics.py`) — as originally reported; superseded,
see the 2026-09-14 correction below:**
- Monthly probabilistic Sharpe: **1.00** (P(true Sharpe > 0) — not a fluke by this measure).
  *Since shown to be P(Sharpe > 0) for momentum AND for every baseline (EW, random top-10 all
  scored ≥0.996 too) — the statistic cannot distinguish selection skill from just owning a
  rising basket of stocks.*
- Sensitivity sweep (6/9/12-month lookback × top 5/10/15, reported as robustness, NOT
  selection — the pre-registered 12mo/top-10 stays the verdict): **9 of 9 neighbor
  specs beat their own EW-universe.** The edge is broad, not a knife-edge config.
  *Since shown to be the sign of a total-return margin, not a significance test — on the
  current 30-name universe zero of nine neighbors clear a real t≥2 bar (best t=1.18).*
- Regime split (by SPY up/down/chop): up +1695%, down −2.0%, **chop −39.1%**. *Raw return —
  a long-only book wins in up and loses in down/chop by construction; see the active-return
  regime table below for what this says about the EDGE, not just ownership.*

**🚩 Red flag (as originally reported):** Loses badly in choppy/sideways markets (−39.1%).
This is a **bull-market vehicle**, not all-weather. *Since shown to be a raw-return artifact —
the corrected (active-return) regime read on the current universe is different; see below.*

**Caveats (read before believing anything above):**
- **Survivorship bias.** The universe is today's ~97 liquid names — every one "survived" to
  2026 by construction. This inflates ALL long-only rows above, including the baselines,
  which is exactly why "beats EW universe" is the bar that matters, not the raw +972%.
- **Single history, one draw.** `n_trials=1` means there's nothing to curve-fit, but it's
  still one specific 7-year period (which happens to include a historic bull run). The
  per-year split, regime split, and probabilistic Sharpe are the scrutiny available; they are
  not a substitute for an out-of-sample period we haven't seen yet — which is what paper
  trading is for.
- **No short leg tested.** The "true" academic momentum thesis pairs winners with a short of
  losers; we test long-only only, by design (shorting isn't practical at this account size).

**Status (superseded 2026-09-13, see the 2026-09-14 correction below):** ~~`SURVIVES the panel
bar; robustness-checked (monthly PSR 1.00, 9/9 sensitivity neighbors beat EW); 1 red flag
tempers it — pending Tenzing sign-off + paper trading.`~~ Current: `UNPROVEN — the edge over
EW-universe is not statistically distinguishable from luck (t=0.34, need ~2+).`

**Verdict:** **ITERATE → paper?** Not yet ADVANCE. Per [[plan/11-strategy-pipeline]] §3 Gate 4,
a green number needs Tenzing's economic story and judgment before it's believed, and
per [[plan/07-charter-what-we-do]] nothing goes to paper trading without it.

## Addendum: robustness cross-check on a different (smaller) universe (2026-07-06)

The universe was deliberately slimmed from ~97 to a curated **30-name core** (see
[[plan/01-decision-log]] 2026-07-06 — quality over quantity, no penny/leveraged names). Re-running
this exact spec (unchanged: 12-1, monthly, top 10, EW, 3/1 bps) on the new 30-name universe is a
genuine out-of-universe robustness check, not a rerun of the same test:

| Portfolio | Total return | Sharpe |
|---|---:|---:|
| Momentum top-10 (30-name universe) | +309.4% | 0.99 |
| EW universe (30 names) | +284.5% | 1.01 |
| Hold SPY | +179.7% | 0.85 |

Still beats EW-universe, random, and SPY on raw return. Monthly PSR still **1.00** *(as
originally reported — see the 2026-09-14 correction below: this is P(Sharpe>0), which the
EW-universe and random top-10 also score ~1.00 on)*. Sensitivity sweep **7/9** neighbors beat
EW on raw-return sign (down from 9/9 on the larger universe) *— since shown to be zero of nine
significant at t≥2 (best t=1.18), see below*. Chop-regime red flag actually improved:
**−22.4%** (was −39.1% on ~97 names) *— raw return; the active (vs EW) regime read is
different, see below*. The headline number moved a lot (+972% → +309%) purely because it's a
smaller, different set of stocks — that's expected and is not a contradiction; both runs are
logged in [[plan/02-verdict-log]].
**Read this as:** the edge isn't an artifact of one specific 97-stock universe — it shows up
again on an independently chosen smaller set. It is still NOT a second independent time period
(same 2019–2026 window both times), so this doesn't touch the "single history" caveat above.

## Cost sensitivity (run 2026-09-14)

**Question:** Over what cost regime does momentum's edge over the EW-universe survive? The 3/1 bps baseline above is plausible for a liquid-ETF account, but commissions or execution friction could push costs higher. This sweep re-runs the canonical spec at four cost levels (spread_bps = total, slippage_bps = 0 for consistency; effective cost per unit turnover = 0.5 × spread_bps):

| Cost regime | Momentum total return | EW-universe total return | Margin | Beats EW? |
|---|---:|---:|---:|---|
| 3 bps (0/3 bps split) | 310.6% | 284.5% | +26.2% | YES |
| 10 bps | 306.3% | 284.5% | +21.9% | YES |
| 25 bps | 297.3% | 284.5% | +12.8% | YES |
| 50 bps | 282.6% | 284.5% | −1.8% | **NO** |

**Verdict:** Momentum's edge over EW persists through 25 bps total cost, but turns negative at 50 bps. For real-money trading, this is a meaningful bound: retail options (300+ bps spread) would be ruin; even equities at 10 bps (0.5 × 20 bps spread, roughly ATM for a micro-cap or high-slippage fill) would leave momentum with a 22% margin. At 50 bps, the premium evaporates — the strategy regresses to the universe. **Cost regime is a first-order input to any real trade.** The canonical xsect.py run uses 3/1 bps (spread_bps=3, slippage_bps=1, effective 2.5 bps per turnover), which is tighter than the "3 bps" row here; the true baseline momentum return at that regime is **309.4%** (from the xsect.py main() output above).

## Gate correction (2026-09-14): the robustness gauntlet was testing the wrong question

A 2026-09-13 significance check (P0.1) found momentum's edge over the EW-universe is not
distinguishable from luck (t=0.34). A follow-up audit
([[research/audits/2026-09-gates]]) found this wasn't an isolated bug: almost every
statistical gate in the codebase — including every "robustness" number reported above — asked
"did this make money?" (vs. zero) instead of "did this beat its benchmark?" A long-only
portfolio in a rising market answers the first question YES regardless of any selection
skill, so **the probabilistic Sharpe, the sensitivity sweep's "N/9 beat EW," and the raw-return
regime/per-year splits above all measured ownership, not edge.** Fixed in `diagnostics.py` and
`xsect.py` (plan/12 tasks P0.4, P0.6, P0.7); this section gives the corrected numbers for the
current 30-name universe (the ~97-name run above cannot be recomputed — that universe was
later slimmed and its raw data is no longer fetched).

**Corrected robustness gauntlet (30-name core, `xsect.py`, run 2026-09-14):**
- **Probabilistic Sharpe, active vs EW-universe: 0.63** (was 1.00 vs zero — the vs-zero number
  is kept only as a reference showing why it's not the gate: EW-universe and random top-10 both
  also score ~1.00 on it).
- **Sensitivity sweep: 0 of 9 neighbors significant at t≥2 (best t=1.18).** 7/9 still have a
  positive raw-return margin vs EW — a point comparison, not evidence of breadth.
- **One-year-wonder (active series): 156% of the seven-year edge over EW came from 2024;**
  the other seven years net to ≤0 in log terms. The raw-return per-year table above (which
  reported "won 5 of 8 years") could not see this because raw return is mostly beta, spread
  evenly across every year.
- **Regime split, active vs EW-universe (SPY up/down/chop, lookahead-corrected trend tag):**
  up −7.8%, down **+16.8%**, chop −1.1% (1171/331/237 bars). This is a different, more precise
  story than "bull-market vehicle": momentum's *edge* is weakest in up markets and chop, and
  actually strongest in down markets — the raw regime numbers above conflated the strategy's
  overall direction (long-only, wins in up markets by construction) with whether *selection*
  added anything in each regime.
- **Significance vs EW-universe (unchanged from the 2026-09-13 finding, now cross-checked):**
  t = 0.34 (Newey-West HAC t = 0.41, correcting for autocorrelation — same conclusion).
  Removing the top contributor (NVDA): **t drops to −0.03** — the edge is not just
  concentrated in one year, it depends on one name.

**Status:** `UNPROVEN` (unchanged from the 2026-09-13 finding — this correction changes *why*
the robustness numbers can't be trusted, not the headline verdict itself, which was already
right). Kill criteria updated in the spec section above: "probabilistic Sharpe < 0.95" →
"active t-stat vs EW < 2".

## What we learned
*[Tenzing — fill in judgment here: real edge or survivorship? Any additional flags? Sign,
amend, or reject, and why.]*

## Next step if signed
1. Tenzing signs (this file, above).
2. Tenzing renders judgment (this file, above). ~~Finish the real cost table~~ Cost sensitivity table now complete (see above).
3. Tenzing generates real Alpaca paper API keys (`.env` is currently blank) and starts
   paper-trading this exact spec via `alpaca_paper.py` for 2+ weeks before any further
   discussion of real money — see [[plan/08-alpaca-setup]].
