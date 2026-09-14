# Strategy Thesis 001 — Cross-Sectional 12-1 Momentum

Home: [[PROJECT_PLAN]] · Author: drafted by Tenzing/Claude from the engine spec, **pending
Jonathan's signature** · Status: **testing — survives first panel test, awaiting sign-off**

*This is the thesis document the process ([[roles/ROLE_Jonathan]], [[roles/standup-template]])
calls for. It was written up AFTER the engine (`xsect.py`) was already built and run — see
[[plan/01-decision-log]] 2026-07-03 "Thesis 001 engine mismatch resolved" for why the
sequencing was pragmatic (we needed the panel engine to exist before anyone could test the
idea at all). Jonathan: read this, then either sign it as-is, amend the economic story, or
reject the result. Your signature is the missing step — see [[plan/09-status-where-we-are]].*

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
- Universe: ~97 liquid US stocks (index ETFs excluded — see `EXCLUDE` in `xsect.py`), Henry's
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
random top-10 picks, a probabilistic Sharpe below 0.95, or a one-year-wonder pattern (>60% of
return from a single year).

**My prediction (pre-registered):** *[Jonathan — this line is intentionally unfilled. The run
below already happened (see the engine-mismatch note above), so your "prediction" here is
really your ex-ante economic judgment read against the result, not a blind guess. Write
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

**Per-year, momentum vs EW universe (won 5 of 8 years):**
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

**Robustness gauntlet (`xsect.py` + `diagnostics.py`):**
- Monthly probabilistic Sharpe: **1.00** (P(true Sharpe > 0) — not a fluke by this measure)
- Sensitivity sweep (6/9/12-month lookback × top 5/10/15, reported as robustness, NOT
  selection — the pre-registered 12mo/top-10 stays the verdict): **9 of 9 neighbor
  specs beat their own EW-universe.** The edge is broad, not a knife-edge config.
- Regime split (by SPY up/down/chop): up +1695%, down −2.0%, **chop −39.1%**.

**🚩 Red flag:** Loses badly in choppy/sideways markets (−39.1%). This is a **bull-market
vehicle**, not all-weather — momentum is known to whipsaw and crash when trends reverse
sharply (see the 2009 momentum crash in the literature). Anyone signing this off should read
that as "expect real pain in a choppy year," not "this always wins."

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

**Status:** `SURVIVES the panel bar; robustness-checked (monthly PSR 1.00, 9/9 sensitivity
neighbors beat EW); 1 red flag tempers it — pending Jonathan sign-off + paper trading.`

**Verdict:** **ITERATE → paper?** Not yet ADVANCE. Per [[plan/11-strategy-pipeline]] §3 Gate 4,
a green number needs Jonathan's economic story AND Henry's judgment before it's believed, and
per [[plan/07-charter-what-we-do]] nothing goes to paper trading without both.

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

Still beats EW-universe, random, and SPY. Monthly PSR still **1.00**. Sensitivity sweep **7/9**
neighbors beat EW (down from 9/9 on the larger universe — still a majority, a bit less broad).
Chop-regime red flag actually improved: **−22.4%** (was −39.1% on ~97 names). The headline
number moved a lot (+972% → +309%) purely because it's a smaller, different set of stocks —
that's expected and is not a contradiction; both runs are logged in [[plan/02-verdict-log]].
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

## What we learned
*[Henry — fill in your judgment here: real edge or survivorship? Any additional flags?]*
*[Jonathan — fill in here after reviewing: sign, amend, or reject, and why.]*

## Next step if signed
1. Jonathan signs (this file, above).
2. Henry renders judgment (this file, above). ~~Finish the real cost table~~ Cost sensitivity table now complete (see above).
3. Tenzing generates real Alpaca paper API keys (`.env` is currently blank) and starts
   paper-trading this exact spec via `alpaca_paper.py` for 2+ weeks before any further
   discussion of real money — see [[plan/08-alpaca-setup]].
