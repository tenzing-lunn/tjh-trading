# 03 — Roadmap (Now / Next / Later)

Home: [[PROJECT_PLAN]] · Status: [[plan/09-status-where-we-are]] (the up-to-date pipeline tracker)

*No dates — we move as fast as we can. This is about order and dependency, not calendar.
Move items up as they're done; add freely. Last refreshed 2026-07-06 against [[plan/09-status-where-we-are]]
and [[plan/01-decision-log]] — the machine track (web app, wide scan, Thesis 001 engine) is
DONE; what's actually "Now" is the human sign-offs, not more code.*

## ▶️ Now
- **2026-09-13 — supersedes the sign-off items below:** Thesis 001's edge over EW-universe
  failed a significance check (t = 0.34). Work now follows [[plan/12-real-markets-plan]]. First
  parallel batch: P0.1 add the vs-EW gate (Opus), P0.2 audit the other gates (Fable), P1.1
  fetch Ken French momentum data (Haiku), P1.3 design a no-hindsight universe (Fable).
  Tenzing: review the **G1 criteria** in plan/12 *before* the results come in.

*The engineering track (web app v1, wide scan, cross-sectional panel engine) is built, run,
and deployed. The bottleneck has moved from code to people — see [[plan/09-status-where-we-are]]
"the one thing blocking everything."*

- **Tenzing:** (1) SIGN Thesis 001 (`research/theses/001-cross-sectional-momentum.md`) — it's
  pre-filled with the run and a surviving verdict attached; own or amend the economic story,
  then pre-register whether to advance it to paper. **Not yet done — first log entry
  still outstanding** ([[roles/log-Tenzing]]). (2) build the real cost table (bps per
  instrument, from actual Alpaca/market numbers) and ratify the **slimmed 30-name universe**
  (`fetch_universe.py`, cut from ~97 on 2026-07-06 — quality over quantity; old list archived,
  not gone, in `realdata_archive_97/`) — `costs.py`'s 3/1 and 300/50 bps regimes are still
  placeholders, not the ratified numbers yet; (3) render a judgment (real vs.
  survivorship-inflated) on Thesis 001's verdict, now checked on **two** universes (see
  [[plan/02-verdict-log]] 2026-07-06). (4) ~~generate real Alpaca paper API keys and fill `.env`~~ **DONE** — `.env`
  has live Alpaca paper keys, account verified ACTIVE (2026-07-10, $100k equity/$400k buying
  power); (5) ~~wire `scan.py`/`xsect.py` results into `verdict_log.py`'s auto-logger~~
  **DONE (2026-07-11)** — `scan.py --log` records edges + gate-2 suspects, `xsect.py --log`
  records the Thesis-001 panel verdict; `verdict_log.render_markdown` dedups per
  (ticker, strategy, run, cost_regime) so re-runs refresh instead of stacking. Refresh the
  human log with `python3 verdict_log.py --write-md plan/02-verdict-log.md`; (6) ~~add the
  panel-⑤ robustness/red-flag view (`diagnostics.py` output) to the per-ticker web app view~~
  **DONE (2026-07-11)** — `export_results.build` now attaches `diagnostics` (deflated Sharpe,
  per-year, regime split, red flags) to each walk-forward entry, and `webapp/app/page.tsx`
  renders a `⑤ Robustness` card in the per-ticker view. Verified live (SPY/meanrev: DSR 0.60,
  one red flag).

## ⏭️ Next
- Once signed off: paper-trade Thesis 001 via `alpaca_paper.py` for 2+ weeks;
  keep a trade journal (thesis, entry, exit, expected vs actual cost).
- Make the deployed app interview-strong: README, architecture notes, demo flow.
- Add the **options modeling layer** to the app only as an approximate teaching overlay; see
  [[webapp/options-modeling]].
- Fill the missing Obsidian notes ([[Strategies]], [[Metrics]], [[Data]], [[Walkforward]] —
  still unresolved wikilinks).

## 🔮 Later
- Intraday Kronos (data swap) — parked; revisit only if we deliberately go intraday.
- Wire Supabase to **record live option chains daily** — the honest path to future options
  backtests.
- Finetune Kronos *only if* zero-shot shows OOS edge (still not run for real — parked per
  [[plan/01-decision-log]] 2026-07-02, daily-bar timeframe mismatch).
- Fordham research-club build-out ([[plan/00-vision]]).
