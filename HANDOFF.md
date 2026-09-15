# Codex handoff — 2026-09-15

Read `AGENTS.md`, `CLAUDE.md`, and `plan/14-intraday-plan.md`. The `.py` files are
canonical for engine logic; plan/14 is canonical for direction. Tenzing owns all
gates. Scope is intraday plus swing; monthly Thesis 001 remains INCONCLUSIVE and
parked. No order commands, paid services, or real-money authorization.

## Completed and committed on main

| Commit | Work |
|---|---|
| `16799f3` | Merged verified I0.3 (`a7dea45`) |
| `59ec472` | Merged I1.1 fetcher (`4181a3d`) and recovery/throttling fixes (`f60af1c`) |
| `20e7c73` | I1.2 quality admission, I1.4 measured spreads, regression tests, audit and plan updates |

Earlier merged foundations: I0.1 `2761a70`, I0.2 `8ca33e5`, I1.3 `f173dc3`,
I1.6 `54e6503`. Original handoff baseline was `81f74d4`.

## Verified results

- **Daily scan: 0 EDGE?, 3 suspect, 76 FAIL, 14 INCONCLUSIVE (93 rows).** I0.3
  comparison found no changed legacy categories or metrics. Suspects remain
  avgo/tsmom, nvda/sma, nvda/tsmom. Effective scan-wide trial count is 94.
- I0.3 sanity 15/15 and ledger 14/14 passed before merging. After data-admission
  integration, the scan headline still matches, `test_ppy.py` passes, and all
  **16 tests** in `test_fetch_intraday.py`, `test_spreads.py`, `test_dq.py` pass.
- API and export imports pass in `.venv`; the earlier system-Python `yfinance`
  import limitation does not apply there. Use `.venv/bin/python` for data work.
- Intraday cache: **32 symbols, 4,128 symbol-months, 42,351,932 bars**. Every
  parquet's row counts match the manifest. No duplicate regular timestamps or
  >20% consecutive one-minute moves were found by the inventory screen.
- Calendar-based I1.2: **98 excluded symbol-days** across six dates; **672 valid
  early-close symbol-days preserved**. All 31 daily CSVs pass. See the full
  exclusion counts and limitations in `research/audits/intraday-data.md`.
- I1.4: **21,094/21,120 valid snapshots**, 24 locked/crossed, two missing. Minimum
  symbol/year/bucket coverage is 90%. Median/p95 quote age: 0.327/4.006 seconds;
  maximum 44.373 seconds. SPY midday median half-spread is **0.170 bps**, below
  the old rough planning expectation. All 32 pooled medians have open > mid > close.
- Both `experiments.jsonl` and `verdicts.jsonl` remain unchanged by verification.

## Data and reproduction

Data was already moved to main `intraday/`; **do not repeat the old move command**.
Vendor data stays ignored. Raw quote snapshots and quality reports are local.

```bash
.venv/bin/python audit_intraday.py
.venv/bin/python dq.py
.venv/bin/python spreads.py               # offline final summary
.venv/bin/python -m unittest test_fetch_intraday test_spreads test_dq -q
LEDGER_DISABLE=1 .venv/bin/python scan.py
```

- `data.load_csv()` validates daily admission after leading pre-IPO trimming.
  A bare daily CSV has no declared vendor start; the validator supports an
  explicit `expected_start` when provenance supplies it.
- `data.load_intraday()` requires an unchanged manifest/file set and SHA-256
  checksums matching `intraday/_quality/<SYMBOL>.json`. It returns separate
  admitted sessions. **Do not concatenate and earn returns across removed days.**
- The calendar helper corrects the 2025-01-09 Carter closure missing from the
  exchange-calendars release available for Python 3.9; official source is in the audit.
- `spreads.py` resumes the frozen plan `f85ba067ce51c73c`, 20 full sessions/year
  over 2016–2026 through September 11. All selected days were calendar-checked.
  The first one-second pass missed quiet quotes; a recorded 60-second lookback
  amendment filled only no-update observations at unchanged sample endpoints.
  Existing invalid observations were retained. Collection and backfill finished.
- Tables: `research_data/spreads.csv`, `spreads_by_year.csv`, `spread_samples.csv`,
  `spreads_manifest.json`; readable aggregate table in `Costs.md`.
- Run one Alpaca collector at a time. The 0.35-second HTTP limiter covers SDK
  pagination/retries but is process-local.

## Next tasks

1. **I1.5 execution-cost proposal and implementation.** Measured half-spreads are
   available. Specify conservative slippage vs participation and date-appropriate
   sell-side fees; explain uncertainty and stress cases. **Tenzing signs constants
   before adoption.** `costs.py` and its daily/options regimes remain unchanged.
   Pooled quote medians are not measured fill costs; consult annual and p95 tables.
2. Phase 2: session/overnight accounting, delayed-feed timing enforced in the
   engine, calendar walk-forward, stress tests, sanity checks, independent audit.
   Checked data does not make the existing daily engine ready for intraday use.
   A minute bar becomes available only after completion, plus the feed delay;
   implement timestamps carefully rather than blindly shifting retained rows.
3. I1.7 independent vendor cross-check remains open. Databento's credit is
   Tenzing's to claim. No paid data or account creation was attempted.
4. Pre-register short-term theses only after the data/engine audit. Every gate
   remains Tenzing's; no strategy currently has permission to trade.

## Operational rules

- Keys stay in ignored `.env`; never print, log, copy or commit them.
- Free by default; paid services require Tenzing's sign-off and the standing
  ~20x justification. No orders, including paper orders, from agents.
- Use `LEDGER_DISABLE=1` for scan/run/xsect validation. `test_ledger.py` uses
  temporary ledgers and must run **without** that flag. Do not discard unrelated
  ledger edits to hide test pollution; inspect changes before committing.
- Check branch bases before worktree work. Co-authored commits include a trailer.

## Worktrees

No worktrees were removed. I0.3 and I1.1 are now merged; I1.6 and I1.3 were already
merged. The old `agent-a5c35dbce339f5e5b` at `fec0955` still needs inspection before
cleanup. Preserve uncommitted files/symlinks when assessing any worktree removal.
Main's `.claude/worktrees/` directory remains untracked local state.
