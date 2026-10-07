# Independent verification of the I1.2 admission corrections

Date: 2026-09-16. Reviewer: GPT-6 Astra, independent of the implementation
agents, following `plan/16-agent-routing.md`. Reviewed the pending `dq.py` and
`test_dq.py` changes on checkout `6f9bfab0acd593986322824f1aefb53b4c3644e2`.
This is an acceptance addendum to
[[research/audits/2026-09-15-independent-data-review]], **not I2.6**.

**Disposition: accept the scoped I1.2 corrections.** The minute gap and daily
absurd-return refusals pass independent checks. An exact +60% false rejection
found during this review was corrected by a separate implementer and independently
retested. No unresolved defect in these corrections was found; this is bounded
acceptance, not a claim that every data-quality or PIT requirement is closed.

Final reviewed SHA-256 identifiers:

- `dq.py`: `6a082e4de4c066670e3c4d073f8573d1a8ec7948e692d9a3e5b8758ec4a84e6a`
- `test_dq.py`: `e47d92cd7e3bc4ea8e950accd6d91dfbf672e74c82fd620fb72f53b69acf837e`

## Independently reproduced admission behavior

All fixture files and fixture certificates were created under Python temporary
directories. Checks called the actual inspection and loading functions, and the
CLI check used the actual `dq.main()` with only temporary working directory and
arguments substituted. No market-data files or real certificates were rewritten.

| Check | Observed behavior |
|---|---|
| Full January 4, 11 and 12, 2016 sessions; January 5–8 absent | Inspection raises `QualityError`, names four consecutive missing sessions and whole-symbol exclusion; no new admitting certificate is created |
| Pre-fix certificate for that same four-session gap, with its recorded run | Loading refuses the whole symbol |
| Same certificate without `longest_missing_session_run` | Loading recomputes from session rows and refuses |
| Request only January 11 onward from the four-gap certificate | Loading still refuses; a requested range cannot bypass symbol admission |
| Full January 4, 8, 11 and 12 sessions; January 5–7 absent | Inspection records three missing sessions; loading returns four separate 390-row frames and preserves the excluded dates in the certificate |
| Three-gap certificate without the recorded run | Legacy fallback still admits the separate sessions |
| Three/four missing sessions spanning the MLK holiday weekend | Three admitted, four refused; weekend and holiday calendar dates do not increase the session count |
| Four missing leading or trailing sessions | Both refused by inspection |
| CLI inspection of the four-gap fixture | Prints `SPY EXCLUDE` with the reason and returns status 1 |
| Valid OHLCV daily file with prices 100 → 300 | Both direct validation and `data.load_csv` refuse explicitly; rows are not repaired or dropped |

To test legacy certificates independently of hand-entered counts, the reviewer
temporarily patched only `refuse_long_session_gap` while producing the old
certificate with `inspect_symbol`, then restored the function before loading.
This reproduces the prior inspection behavior and retains real file hashes,
manifest hashes and calendar-derived session rows.

## Daily boundary finding and re-verification

The first proposed daily implementation used `pct_change().abs() > .60`.
For closes 100 and 160, the computed return is `0.6000000000000001`; it refused
an exact +60% move despite the stated **greater than 60%** rule. The independent
fixture admitted 159.999999 and 40, and refused 160, 160.000001, 39.999999 and
300. This is a false rejection at the positive boundary, not an optimistic
admission of a bad seam.

The final implementation permits one representable floating-point step above
0.60 (`np.nextafter(.60, np.inf)`) to accommodate division rounding, while
separately rejecting nonfinite returns. This is numerical tolerance, not an
economically meaningful expansion of the threshold. Independent re-verification
used 13 cases, each through both direct validation and a real temporary CSV
load, for **26 passing admission checks**:

- Exact +60% and −60% moves at starting prices 100, 10 and 1: admitted.
- 100 → 160.000001 and 100 → 39.999999: refused.
- 100 → 159.999999 and 100 → 40.000001: admitted.
- 100 → 300 and 100 → 1: refused.
- Individually finite positive prices whose ratio overflows to infinity: refused.

## Regression evidence and limits

- `.venv/bin/python -m unittest test_fetch_intraday test_spreads test_dq -q`:
  all **21 tests passed** after the numerical-boundary correction (19 before it).
- `.venv/bin/python dq.py --daily-only`: all 31 real daily CSVs admitted, each
  with 2,010 bars. This path performs no minute recertification.
- Read-only review of the 32 existing minute certificates: maximum recorded
  missing-session run is one; every count matches recomputation from its session
  rows. The prior independent review already verified all 42,351,932 minute bars
  and 4,128 file hashes; repeating that inventory is unnecessary for this patch.
- Engine timing, train-only selection and slice-safe metrics are outside this
  patch. `backtest.py` still shifts positions and subtracts costs; the corrections
  do not modify engine mathematics.
- Independent `.venv/bin/python scan.py` with `LEDGER_DISABLE=1` and without
  `--log`: **0 EDGE?, 3 suspect, 76 FAIL, 14 INCONCLUSIVE**, totaling 93 rows
  across 31 daily names and three strategies; existing family count charged
  **N=94**. Runtime was 88 seconds. This scan ran on the initial admission fix;
  the final numerical correction then re-admitted all the same 31 daily files.
  It changes only an admission boundary, not the frames or backtest calculations.
  Both actual ledger SHA-256 hashes were asserted identical before and after
  the scan:
  `experiments.jsonl` = `a660d406d608b5db112e2dc4b3af68cea74f93b31351d9cbe0ce167d40a8c057`;
  `verdicts.jsonl` = `71f94110e72d4b8e8bc8e0c855bc65c3679523ce11752025e849f1a3c32e901b`.

`LEDGER_DISABLE` controls the experiment ledger only. Omitting `--log` keeps
this scan from writing verdicts; the environment flag alone is not a general
guarantee that other entry points, such as `run.py`, leave verdicts unchanged.

Only the two admission defects identified in the earlier interim review are
under acceptance here. The older **PIT pipeline repairs remain open**:
`fetch_pit_prices.load_prices` and `pit_panel.build` do not acquire these daily
checks merely because `data.load_csv` calls them. The WRK/PARA/TMUS/SW defects,
vendor-span validation, fill seams and implausible adjusted-price histories need
their own implementation and verification. A >60% adjacent-return screen does
not prove an entire price history is economically plausible.

**I1.7 remains open:** none of this is a second-vendor bar comparison. No
execution constants, trading decision or human gate is approved. No data cache,
quote cache, experiment ledger or verdict ledger was changed by this reviewer.
