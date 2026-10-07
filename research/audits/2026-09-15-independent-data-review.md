# Independent interim review: I1.2 data admission and I1.4 spreads

Date: 2026-09-15. Reviewer: independent orchestrator-verifier (GPT-6 Astra),
separate from the implementation agents. Reviewed implementation: `20e7c73`;
checkout at review start: `6f9bfab`. The reviewed `dq.py`, `data.py`, `spreads.py`,
`test_dq.py`, and `test_spreads.py` matched `20e7c73` exactly. Line references below
refer to that revision unless stated otherwise. Later corrections need a separate
verification addendum.

**Result:** the local minute inventory and quoted-spread measurements reproduce.
I1.2 is not fully fail-closed as specified: the minute long-gap refusal is missing,
and the claim that this closes the older PIT seam/price-corruption fixes is wrong.
I1.4 is usable as descriptive quote evidence for an I1.5 proposal, with explicit
sampling limits and separate admission checks in the future cost consumer.

This is **not I2.6**, a trading verdict, approval of execution-cost constants, or
approval to trade. No implementation, ledger, credentials, or vendor cache was
changed by this reviewer. All computations were offline in `.venv/bin/python`.
Temporary fixtures were removed by `TemporaryDirectory`.

## Findings

### 1. WRONG — medium: the minute >3-session gap criterion is not enforced

**Spec:** plan/14 I1.2(d) requires refusing a file with a gap exceeding three
trading days. Its symbol-day amendment explicitly changes criterion (a), sparse
sessions; it does not remove criterion (d).

`dq.py:153` computes the missing-session mask and `dq.py:158` records its longest
run. `load_intraday` checks stale certificates and late starts (`dq.py:178`,
`dq.py:180`) but never checks the run length. The CLI increments failures only for
late starts (`dq.py:215`). A four-day missing interval therefore produces a
certificate and a successful load.

**Independent reproduction:** create proper January 2016 parquet/manifest data
with full sessions on January 4, 11, and 12 only. January 5–8 are four consecutive
missing trading sessions. `inspect_symbol` returns
`longest_missing_session_run=4`; `load_intraday` returns January 4, 11, and 12.
See executable reproduction A below.

**Impact:** this is a real admission/specification mismatch. It is **not evidence
of fabricated gap returns**: the loader returns separate session frames, which
is the right protection at this layer. None of the current 32 certificates has
a missing run exceeding three, so this reproduction does not disqualify the
current inventory. Future bad files could be admitted contrary to the rule.

**Required correction:** reject such certificates at load time and report a
symbol-level failure in the inspection CLI. Test the four-session failure and
the three-session boundary through real inspection plus loading, retaining
separate-session handling of ordinary sparse days.

### 2. WRONG — high for PIT evidence, medium for daily admission: the older seam fixes remain open

`validate_daily` (`dq.py:65`) checks timestamps, candle structure, calendar gaps,
and an optional expected start. It has no adjacent price-jump or implausible
price-history check. Three valid OHLCV daily bars with a +200% jump are admitted.
This fixture alone does not prove every large price jump is corrupt; it proves
the advertised corruption screening is absent.

More decisively, the **actual prior defects still reproduce** on local PIT data:

| Read-only reproduction | Observed result |
|---|---|
| `fetch_pit_prices.load_prices('WRK')` | One row is still accepted |
| `load_prices('PARA').close.max()/close.min()` | 95,904.8521 |
| Largest absolute daily change in `load_prices('TMUS').close` | 107.9392% |
| `pit_panel.build(verbose=False)`; SW July 3, 5, 8, 2024 | `1.0 → 51.51 → 1.0`, including +5051% |

`fetch_pit_prices.py:366` directly reads CSVs and accepts any nonempty frame;
`pit_panel.py:102` uses that loader, and `pit_panel.py:154` still fills missing
cells with 1.0. These paths **do not call `data.load_csv`**. Integration at
`data.py:49` therefore cannot close their defects.

The original requirements in `research/audits/phase1.md:249` are specific:
validate against Tiingo's declared span; prevent a synthetic 1.0 cell from
touching a real bar; add a held-cell absolute-return >60% acceptance screen;
exclude absurd adjusted-price histories. The audit supplies **no numerical
max/min threshold** for the latter. A newly chosen ratio threshold must not be
described as a pre-existing specification.

**Impact and scope:** the plan/14 assertion that I1.2 closes P1.4 items 1, 3, and 4
is false. Prior PIT quantitative evidence remains provisional. These are largely
pre-existing defects, not a regression in I1.4 and not evidence that the 32-name
minute cache contains the same faults. A conservative daily seam screen improves
the new admission boundary but does not itself fix the PIT fill algorithm.

**Required correction:** qualify the completion claim now. Keep PIT fetch-span,
seam-construction, and corrupt-series fixes open until those actual code paths
and actual fault fixtures are checked. Implement any daily screen as a rejection
with an explicit reason; do not silently repair or drop a real large move.

### 3. CONFIRMED, with medium-severity limits on use — I1.4 measures sparse quoted spreads

`spreads.py:74` selects the latest update, including an invalid latest update;
it does not search backward for a favorable valid quote. The half-spread formula
at `spreads.py:90` is correct. Backfill (`spreads.py:106`) affects only no-update
samples at fixed endpoints. Missing/locked/crossed quotes do not become zero
spread. Completed backfill is required when its amendment exists.

I recomputed every valid observation from cached bid/ask prices, checked sample
source/feed/window and quote ages, and independently rebuilt pooled medians,
means, and p95s. Maximum aggregate discrepancy from the saved CSV was
`1.7763568394002505e-15` bps. The frozen plan hash recomputes to
`f85ba067ce51c73c`.

**Limits relevant to I1.5 adoption:**

- Each annual symbol/bucket contains only 18–20 valid snapshots. Annual p95 is
  supported by roughly one upper-tail observation, not a precise tail-cost
  estimate. There are 220 shared sampled dates, not 21,094 independent market
  regimes; symbols and buckets share market conditions.
- `make_plan` (`spreads.py:44`) conditions on SPY having at least 380 distinct
  regular bars and on full calendar sessions. Early closes and poor-coverage
  SPY days are outside the sample. Systematic date spacing is reproducible but
  does not establish coverage of unusual execution conditions.
- Uniform clock-time snapshots are not strategy-execution-weighted samples.
  A strategy trading on volatility spikes may face higher spreads. Quotes also
  do not establish realized fill slippage, market impact, or auction costs.
- Pooled 2016–2026 costs include information unavailable during early historical
  folds. A fixed retrospective cost scenario can be labeled as such; claiming
  causal, historically estimated costs requires a training-only calibration
  policy. Using a whole calendar year's estimate within that year has the same
  future-information issue. No future engine implementation was audited here.
- Annual variation is real: SPY midday median is 0.237486 bps in 2016 and
  0.081832 in 2025, versus 0.170 bps pooled. Pooling hides this variation.

**Disposition:** these do not invalidate the quoted-spread table. I1.5 should
name its calibration policy, use explicit stress scenarios, and keep model
constants subject to Tenzing's sign-off. The old rough SPY expectation is not
a target to force onto valid observations.

### 4. CONFIRMED descriptive behavior; UNCLEAR future admission — completed sampling is not coverage admission

`summarize` (`spreads.py:139`) refuses missing cache files and partial backfills,
but it can successfully publish a completed plan with zero valid samples and
NaN median costs. The low-coverage check at `spreads.py:185` only prints a count.
Independent one-window reproduction returned
`{'coverage': 0.0, 'median_half_spread_bps': nan}` without an exception; output
writers were mocked so no real artifacts changed.

This is acceptable for a descriptive report that honestly shows missingness;
it is not proof that the result can be admitted as an execution-cost model.
The current dataset is not affected (minimum annual bucket coverage is 90%).
The I1.5 consumer must reject missing/nonfinite costs and enforce its stated
coverage/provenance policy. Do not imply the current I1.4 tests already prove
that property. Severity: **medium if consumed without checks**.

## Independently confirmed local evidence

| Check | Result |
|---|---|
| `python -m unittest test_fetch_intraday test_spreads test_dq -q` | 16 tests passed |
| SHA-256 of every certified minute file and manifest | 4,128 files; zero mismatches |
| Reread all parquet data, rerun `inspect_sessions`, compare each certificate | 42,351,932 bars, 32 symbols; zero session-report mismatches; 52.4 seconds |
| Admitted/excluded sessions | 85,950 PASS; 98 EXCLUDE |
| Excluded reasons | 93 below 60% coverage; five missing sessions |
| Early closes | 672 PASS |
| Actual daily CSV admission | All 31 `realdata/*.csv` load |
| Spread observations | 21,094 valid; 24 locked/crossed; two no-update |
| Annual symbol/bucket minimum coverage | 90% |
| Quote-age median / p95 / maximum | 0.3267645 / 4.00564795 / 44.373 seconds |
| Pooled open > midday > close median | 32 of 32 symbols |

The excluded symbol-day counts reproduce exactly: 2018-05-02 (10), 2018-05-03
(10), 2021-04-19 (21), 2021-10-25 (19), 2022-01-24 (17), 2022-03-08 (21).
This independently confirms implementation output, not a second-vendor check;
I1.7 remains open.

## Tests and engine invariants

The existing seven quality tests cover early closes/DST, a calendar closure,
sparse sessions, extreme consecutive minute returns, duplicates, short/daily
gaps, unchecked/stale certificates, and changed file bytes. They do **not** test
the minute >3-session admission path or actual `inspect_symbol`→loader
certification. The loader test at `test_dq.py:73` hand-constructs its certificate.
No existing test exercises daily absurd seams or the PIT faults above.

The six spread tests cover units, latest-quote selection, invalid/missing quotes,
absent windows, backfill preservation, and incomplete backfill. They do not
establish statistical representativeness or cost-consumer admission.

The reviewed change leaves the existing engine's `held = pos.shift(1)`
(`backtest.py:17`), net cost subtraction, and train-only parameter selection
unchanged. Returning sessions separately is appropriate. Minute bars with
internal holes can still pass 60% coverage; `dq.py:104` checks extreme returns
only when timestamps are exactly one minute apart. These are disclosed limits,
and Phase 2 must use actual timestamps and explicit session/overnight handling.
Simply shifting retained rows is not a wall-clock delay. No intraday engine
readiness or strategy edge is established by this review.

## Concrete reproductions against the reviewed revision

### A. Four missing minute sessions admitted

```python
import json, tempfile
from pathlib import Path
import pandas as pd
from dq import schedule, inspect_symbol, load_intraday
from test_dq import bars

s = schedule('2016-01-04', '2016-01-12')
frame = pd.concat([bars(s.iloc[i]['open'], 390) for i in (0, 5, 6)],
                  ignore_index=True)
frame['regular'] = True
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'SPY').mkdir()
    frame.to_parquet(root / 'SPY/2016-01.parquet')
    rec = dict(status='ok', source='alpaca', feed='sip', adjustment='all',
               rows=len(frame), regular_rows=len(frame),
               retrieval_time='2016-01-12T23:00:00+00:00')
    (root / 'manifest.json').write_text(json.dumps({'SPY': {'2016-01': rec}}))
    report = inspect_symbol('SPY', root=root)
    print(report['longest_missing_session_run'])  # 4
    print(list(load_intraday('SPY', root=root)))
    # ['2016-01-04', '2016-01-11', '2016-01-12']
```

### B. Daily seam admission and actual PIT seam

```python
import pandas as pd
from dq import validate_daily
from test_dq import bars
import pit_panel

d = bars('2024-12-02', 3).set_index('timestamp')
d.index = pd.to_datetime(['2024-12-02', '2024-12-03', '2024-12-04'])
d.loc['2024-12-03':, ['open', 'high', 'low', 'close']] *= 3
validate_daily(d)  # returns without error despite +200% seam
p, _, _ = pit_panel.build(verbose=False)  # local cache only
print(p.loc['2024-07-03':'2024-07-09', 'SW'])
# 1.00, 51.51, 1.00, 1.00
```

**Review disposition:** correction and independent re-verification of finding 1
are required before calling I1.2 complete. Finding 2 requires qualifying the PIT
closure claim and retaining its fixes as open work. I1.4 arithmetic is confirmed;
I1.5 may be drafted from it subject to findings 3–4 and the human constants gate.
