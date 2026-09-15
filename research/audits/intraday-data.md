# Intraday data inventory — 2026-09-14

## I1.1 verification

`python3 audit_intraday.py` scanned every local parquet using DuckDB. This is an
inventory and anomaly screen, **not** the I1.2 admission gate.

- 32 symbols, 129 months each, January 2016–September 2026.
- All 4,128 manifest entries are `ok`; every file's total and regular-row counts
  match its manifest entry. No `empty` month currently needs a retry.
- 42,351,932 total bars; 33,337,098 flagged regular bars.
- Median flagged regular bars per day: 388 for COST/GOOGL; 389 for ADBE/AVGO/LLY;
  390 for the other 27 symbols.
- Zero duplicate regular timestamps within symbol/session.
- Zero absolute close-to-close returns above 20% between consecutive regular
  bars exactly one minute apart within the same session. This does not test
  overnight moves or returns across missing bars.
- 522 symbol-days have fewer than 234 flagged bars. This count includes valid
  early closes and must **not** be interpreted as 522 corrupt sessions.

Detailed local tables: `research_data/intraday_audit/{symbols,sessions,extreme_returns}.csv`.
Vendor-derived files remain ignored by Git. Reproduce with `audit_intraday.py`.

## Fetcher review and corrections

The original `4181a3d` fetcher was corrected in `f60af1c` before integration:

- Throttle at the SDK's HTTP request boundary, including pages and retries.
  Sleeping once per month did not bound internal pagination requests.
- Retry past `empty` months and missing parquet files. Persist empty results
  immediately; refuse to overwrite an existing good cache with an empty refresh.
- Use half-open timestamp partitions when writing future responses, avoiding
  possible overlap at inclusive API endpoints.
- Declare the Alpaca SDK dependency alongside DuckDB and PyArrow.

Three offline regression tests cover HTTP throttling, cache recovery, partition
boundaries, and empty-refresh protection. Existing bar files were not rewritten.

## I1.2 results — verified 2026-09-14

`dq.py` recomputes regular-session membership using XNYS scheduled open/close
times. The fetcher's original 09:30–16:00 flag also includes post-close bars on
early-close days, so it is not an admission rule.

The full run inspected 2,689 expected sessions for each of 32 symbols. It excluded
**98 symbol-days**: 93 below 60% coverage and five wholly missing. Exclusions:

| Date | Affected symbols |
|---|---:|
| 2018-05-02 | 10 |
| 2018-05-03 | 10 |
| 2021-04-19 | 21 |
| 2021-10-25 | 19 |
| 2022-01-24 | 17 |
| 2022-03-08 | 21 |

All 672 expected early-close symbol-days passed, as did all 31 daily CSVs. No
symbol began late relative to the first expected 2016 session; no missing-session
run exceeded three days. A checked SPY load for 2024-11-29 returned exactly 210
bars, ending 12:59 New York time.

Certificates in `intraday/_quality/` bind the manifest and parquet file contents
to SHA-256 hashes. `data.load_intraday()` rejects unchecked/changed data and returns
a mapping of separate admitted sessions. `data.load_csv()` now validates daily
files after the existing leading pre-IPO trim. It rejects malformed candles,
duplicate/unordered dates, interior zero volume, non-session dates, long gaps,
and single-bar files. A daily CSV alone does not declare a vendor start date:
`validate_daily(expected_start=...)` supports that check when provenance supplies it.

The library release available under Python 3.9 omits the 2025-01-09 Carter closure;
the calendar helper corrects it using the [NYSE notice](https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf).
Tests cover that closure, DST, early closes, partial and absent sessions, corrupt
bars, daily file admission, and changed-file rejection. No split-date exemption is
applied to adjusted SIP minute bars: an extreme move must be reviewed, not waived
automatically. Phase 2 still must implement session boundaries and feed delay;
these checks alone do not make the existing daily engine an intraday engine.

## I1.4 measurement design

`spreads.py` freezes a dated plan before requesting quotes: twenty evenly spaced
full SPY sessions per year, one deterministic uniform timestamp in each of
09:30–10:00, 10:00–15:30, and 15:30–16:00 New York time. The current plan has
660 windows × 32 symbols, covering 2016–2026 through September 11.

The first one-second pass had 5,250 no-update observations. Before backfilling,
the amendment in `backfill-plan.json` fixed a 60-second lookback at the **same**
sample endpoints, clamped to the bucket start, only for no-update observations.
Existing valid or locked/crossed samples were not replaced. Each sampled day
has equal weight. New plans explicitly filter calendar full sessions; the saved
220 sampled days were independently checked and all were full sessions.

Final coverage: **21,094/21,120 valid (99.88%)**, 24 locked/crossed, two still missing.
Every symbol/year/bucket has at least 90% coverage. Across all timestamped samples,
median quote age is 0.327 seconds, 95th percentile 4.006 seconds, maximum 44.373
seconds. Missing or invalid observations never become zero spread. Tables cannot
be regenerated partway through backfill. These remain sparse quote snapshots,
not executed fills, slippage, auction costs, or stress-event coverage.

All 32 symbols have open > midday > close median half-spreads over the whole
sample. SPY midday is **0.170 bps**, below the plan's rough 0.5–1.5 bps expectation;
the expectation was not a fitted target. A one-cent full spread at a $300 price
has a half-spread of about 0.167 bps. See the full table in `Costs.md`. Use annual
tables as well: pooled 2016–2026 estimates hide changes in prices and liquidity.

Half-spread in bps is `(ask - bid) / (ask + bid) * 10_000`.
The plan and samples stay in `research_data/spread_samples/`; the CLI refuses to
publish its summary until every planned window is cached. It resumes interrupted
fetches and throttles pagination as well as top-level requests. Run one collector
at a time because the limiter is process-local.

References: [Alpaca historical quotes](https://docs.alpaca.markets/us/reference/stockquotes-1)
and [Alpaca Python historical-data client](https://alpaca.markets/sdks/python/api_reference/data/stock/historical.html).
