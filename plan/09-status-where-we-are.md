# 09 — STATUS: Where We Are (living tracker)

Home: [[PROJECT_PLAN]] · Charter: [[plan/07-charter-what-we-do]] · Decisions: [[plan/01-decision-log]]

*The single "where are we right now" page. Update this whenever a stage moves. If you (or
Claude) are catching up cold, read this first, then the charter. Last updated: 2026-07-06.*

## The mission, in one line
Find ONE signal that beats buy-and-hold OOS net of realistic costs on real equity data, prove
it honestly, and make the proof visible. We have **zero survivors so far** — that's expected.

## The pipeline and where each stage stands
Legend: ✅ done · 🟡 in progress · ⬜ not started

| Stage | What it means | Status |
|------|----------------|:--:|
| **1. Harness** | costs/backtest/walkforward/metrics; no-lookahead verified | ✅ |
| **2. Real data in** | adjusted daily bars via `fetch_data.py` (yfinance) or `fetch_alpaca.py` | 🟡 (universe SLIMMED ~97 → **30-name curated core** + SPY via `fetch_universe.py` on 2026-07-06 — quality over quantity, junk/leverage cut; old ~97 archived in `realdata_archive_97/`, not deleted; Tenzing to ratify) |
| **3. First reasoned strategy** | Tenzing writes a thesis with a *why*, then implements it | 🟡 (Thesis 001 IMPLEMENTED + RUN 2026-07-03 — `xsect.py` panel engine + `time_series_momentum`; thesis doc now exists at [[research/theses/001-cross-sectional-momentum]] (written 2026-07-06); **awaiting Tenzing's signature** to close the loop) |
| **4. Run + verdict** | run harness on a liquid ticker, record OOS-net-of-costs vs SPY | 🟡 (Thesis 001 is **UNPROVEN**, not a survivor — 2026-09-13 found the edge over EW-universe is not distinguishable from luck (t=0.34, 30-name core); a 2026-09-14 audit found the "PSR 1.00"/"9/9 then 7/9 neighbors beat EW"/raw-return-regime numbers below were all testing "did this make money" not "did it beat EW", so none of them were real evidence either — corrected: active PSR 0.63, 0/9 sensitivity neighbors significant (best t=1.18), 156% of the edge from one year (2024), t drops to −0.03 ex-NVDA. Raw totals (kept for record): +972% vs +265% EW on ~90 names (2026-07-05), +309% vs +285% EW on the 30-name core (2026-07-06), both beat SPY+random on raw return. Wide scan: 0/309 (100-name) then 0/93 (30-name) clean single-name edges — that null still holds after the same gate fix (`scan.py`, P0.6). See [[research/theses/001-cross-sectional-momentum]] and [[research/audits/2026-09-gates]]. Tenzing's judgment + sign-off before ADVANCE) |
| **5. Web app v1** | Next.js + FastAPI visualizer; restyle to `webapp/MOCKUP.html` | ✅ (LIVE full-stack: https://webapp-zeta-liart.vercel.app + Render backend. 2026-07-03: restyled to mockup, defaults to real SPY, shows the real track record + Thesis 001. **2026-07-06: Engine Room added (`/engine`)** — `scan.py` + `xsect.py` wired into the live API via `engine_api.py` (self-populating data: Alpaca first, yfinance fallback, per-ticker provenance shown), every gate pass/fail expandable per row, plus a live Alpaca paper-account panel (correctly shows zero positions until stage 7 starts). Deploy note: Render needs `APCA_API_KEY_ID`/`APCA_API_SECRET_KEY` set in its dashboard before the deployed backend can use Alpaca — until then it degrades to yfinance-only) |
| **6. Kronos for real** | run `forecast_kronos.py` non-mock on real tickers, read OOS row | ⏸️ **PARKED** — Kronos is strongest *intraday*; we trade *daily swing*. Only revisit if we ever choose to go intraday (phase-2 scope change, not made). See [[plan/01-decision-log]]. |
| **7. Paper trade survivors** | only a strategy that passes stage 4 → `alpaca_paper.py` for weeks | ⬜ |
| **8. Real money** | deferred decision; nothing until a survivor proves out on paper | ⬜ |

## The one thing blocking everything
**2026-09-13 update: proof, before sign-offs.** A significance check found Thesis 001's edge
over EW-universe is not distinguishable from luck (t = 0.34 on the 30-name core; it loses
ex-NVDA). Stage 4 is downgraded to *unproven*. **2026-09-14 update:** a follow-up audit found
the robustness numbers (probabilistic Sharpe, sensitivity sweep, regime split) that were
reported alongside the original 2026-07 run were *also* testing the wrong question (raw
return vs. zero instead of active return vs. EW-universe) — corrected numbers and the fix
list are in [[plan/12-real-markets-plan]] Phase 0, and [[research/theses/001-cross-sectional-momentum]]
carries the full corrected gauntlet. The next work is Phase 1 (long-history and no-hindsight
tests). The paragraph below is the pre-2026-09-13 view, kept for history.

**Human sign-off, not the machine (pre-2026-09-13 view, superseded above).** The first
reasoned strategy (Thesis 001, cross-sectional momentum) is implemented AND run —
~~it survives its first panel test~~ (now: UNPROVEN, t=0.34). What's missing is people:
Tenzing signs the thesis and judges the verdict (real-or-survivorship), then paper trading
via `alpaca_paper.py` (needs Alpaca keys).

## Stack (decided)
- **Broker/data:** Alpaca (Trading API, paper). Shared paper account via API keys. Setup: [[plan/08-alpaca-setup]].
- **Data:** yfinance or Alpaca, daily, split/dividend-adjusted. Liquid equities/ETFs first (SPY/QQQ/IWM + large caps).
- **Holding style:** swing (daily bars, hold days–weeks). Intraday = researched phase-2.
- **Repo:** GitHub `10zinglunn-afk/tjh-trading`, branch `main` (feat/webapp-v1 merged 2026-07-02; work merges to main same session it stops). Web app on Vercel; Supabase later (Phase B).
- **Collaboration:** Notion as the front door (theses, tasks, verdict view); repo canonical for code.

## Who's doing what next
- **Tenzing:** ✅ universe (slimmed 97→30, 2026-07-06) · ✅ Notion (restructured 2026-07-06) · ✅ auto-logger · ✅ full-stack deploy (2026-07-03) · ✅ mockup restyle · ✅ tsmom + `xsect.py` panel engine built and run (2026-07-03, re-run on slimmed universe 2026-07-06). Left: SIGN Thesis 001 (it's pre-filled AND now has a run + surviving verdict attached — review the economic story and own or amend it); real cost table (bps per instrument) + tradable universe + interpret/benchmark verdicts; add Alpaca paper keys; wire `scan.py`/`xsect.py` into the auto-logger.

## Open questions still on the table
- Equities-first vs push toward options sooner (not yet ratified).
- If/when real money ever enters (deferred).
- Multiple-testing correction (deflated Sharpe / trial count) before scaling the universe.
