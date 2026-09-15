# 03 — Roadmap (Now / Next / Later)

Home: [[PROJECT_PLAN]] · Active implementation plan: [[plan/14-intraday-plan]]

Updated 2026-09-15. The short-term intraday/swing plan supersedes the older
monthly-momentum-to-paper sequence. Thesis 001 is INCONCLUSIVE and parked.

## Now

- Phase 0 is complete: three-way evidence gate, frequency-aware annualization,
  and removal of the hard trades-per-fold verdict rule.
- Data foundation: adjusted SIP minute fetcher merged; all 32 symbols inspected.
  The quality gate excludes 98 bad symbol-days and preserves early closes.
  Daily CSVs validate on load; minute loads require matching quality reports.
- Spread measurements are complete: 21,094 valid snapshots; full tables and
  limitations in [[Costs]] and [[research/audits/intraday-data]].
- **Next implementation task: I1.5**, an intraday execution-cost regime using
  measured spreads, stated slippage/participation assumptions and sell-side fees.
  Prepare a concrete proposal; **Tenzing signs constants before adoption**.
  Existing daily and options regimes remain unchanged.

## Next

- Phase 2: session/overnight accounting, the 15-minute feed delay in the engine,
  calendar walk-forward folds, stress tests, sanity checks, independent audit.
  Checked minute data is not evidence that the daily engine already handles this.
- I1.7 independent vendor cross-check remains open. Databento's signup credit is
  Tenzing's to claim; no paid data or account creation without his authorization.
- Pre-register a small set of short-term theses only after the engine audit.
  Every go/no-go gate remains Tenzing's; no order commands.

## Later

- Replay → shadow → paper, with a separate risk gate and kill switch.
- Intraday Kronos zero-shot under the audited delay/cost pipeline; finetuning
  only if zero-shot survives. See [[plan/14-intraday-plan]].
- Web-app presentation, architecture/demo documentation, and missing Obsidian notes.
- Educational options modeling remains paper-only; no outside capital.
