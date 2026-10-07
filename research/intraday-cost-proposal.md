# I1.5 intraday costs — unsigned proposal, 2026-09-17

Implementation is opt-in research code; independent review and Tenzing's adoption
are separate gates. **Human signature: pending. No adopted INTRADAY singleton.**
The legacy `CostModel` and daily/options regimes are unchanged.

## Concrete proposed constants

| Choice | Proposal | Reason / limitation |
|---|---:|---|
| Quoted half-spread | symbol × bucket p95 | More adverse than pooled median; sparse snapshots are not fill observations |
| Slippage floor | 1 bp per side | Policy assumption, not estimated from fills |
| Participation coefficient | 25 bps × sqrt(shares/reference volume) | Explicit adverse-fill allowance; no claim of empirical calibration |
| Capacity | refuse above 5% | Prior volume cannot guarantee future liquidity |
| Minimum quote coverage | 90% | Refuse insufficient bucket coverage |
| Minimum causal history | 20 prior samples | About one sampled year; early history must refuse, not backfill from future |
| Sell fee rounding | ceil each positive component to cents | Conservative research assumption, not a broker invoice specification |

Per-side execution cost is raw notional × (quoted half-spread + 1 + 25√p)/10,000,
where p is shares/reference volume. Slippage alone is 1.791, 2.768, 3.500 and
6.590 bps at participation 0.1%, 0.5%, 1% and 5%. Both entry and exit pay it.
Sell-side fees are added separately. Before any strategy verdict, stress the
coefficient to 50, floor to 2, and spread quantile to 0.99, separately and jointly;
these stress settings are proposed requirements, not completed strategy runs.
No cost coefficient is tuned against strategy returns.

## Reproduce the concrete table

From the project root, run `.venv/bin/python costs.py`. It reads the real local
I1.4 snapshot artifacts, does not fetch data, place orders or write ledgers.
Price, shares and volume below are **hypothetical raw inputs**, not claims about
historical SPY bars: 50 shares at $500, 10,000-share prior reference volume,
2024-06-03. Both sides use the same illustrative price.

| Bucket | p95 half-spread bps | Slippage bps | Buy bps | Sell bps | Round-trip bps | Dollars |
|---|---:|---:|---:|---:|---:|---:|
| Open | 0.345026 | 2.767767 | 3.112793 | 3.396793 | 6.509586 | 16.273965 |
| Midday | 0.269619 | 2.767767 | 3.037386 | 3.321386 | 6.358773 | 15.896932 |
| Close | 0.256446 | 2.767767 | 3.024213 | 3.308213 | 6.332425 | 15.831063 |

Sell fees are $0.70 Section 31 + $0.01 TAF for the $25,000 sale.
Open round-trip cost exceeds midday by 0.150813 bps. Legacy 3/1 bps is 5 bps
round-trip. Neither table is strategy performance or a measured fill-cost claim.

Frozen plan: `f85ba067ce51c73c`. Sample SHA-256:
`8fad9510aaa36c42735db7ea6027986e19a2a4162cad01731c050a6654b81c7e`.
CSV: `research_data/spread_samples.csv`; provenance:
`research_data/spreads_manifest.json`. The model checks the sample digest, plan
hash, exact row coverage, statuses and completed backfill. Rebuilding a changed
artifact requires a new explicit reviewed digest.

## Causality and data limitations

The printed table deliberately uses **retrospective** pooled 2016–2026 quotes;
it is not admissible OOS evidence. `causal` mode admits sample values only from
strictly earlier dates, with the minimum history above. Even that does not make
the retrospectively constructed sampling plan point-in-time: historical universe
selection and sampling design remain limitations. Sparse annual snapshots cannot
establish stressed-day execution quality or price improvement. Coverage is checked
within the eligible symbol/bucket history, not a claim of dense minute coverage.

The current Alpaca cache uses adjustment ALL. Do not pass adjusted historical
prices/shares/volume as raw execution units. A raw companion dataset or audited
corporate-action conversion is a Phase 2 prerequisite. The explicit
`inputs_are_unadjusted=True` assertion is a caller contract, not automatic proof.
Full current-bar volume is forbidden for causal sizing. Prior-bar/profile volume
must have a real availability timestamp no later than the order: a 09:30 minute
bar completes at 09:31 and arrives at 09:46 with the 15-minute delayed feed.
The cost model checks supplied availability; Phase 2 must derive it from feed
provenance, schedule execution by timestamps across gaps, and enforce the delay.

The estimator rejects closed-market timestamps and entire early-close sessions
because I1.4 calibrated full sessions only. It does not model halts, auctions,
borrow, margin interest, taxes, commissions, other broker/exchange charges,
partial fills, order rejection or guaranteed capacity. These omissions prevent
claiming full broker reconciliation; paper-fill calibration remains a later gate.
It refuses legacy `cost_fraction(turnover)` integration because that API lacks
side, time and actual share/price/volume provenance.

## Regulatory sources and scope

Official sources checked 2026-09-17. The intentionally frozen supported interval
is 2016-01-01 through 2026-09-16; sells outside it fail closed. Section 31 uses
charge dates; this draft treats regular exchange execution date as charge date,
not settlement date. It is scoped to ordinary covered exchange equity sales.
Broker pass-through, special exemptions and reporting conventions must be
reconciled before deployment. The schedules are historical facts; penny rounding
is explicitly a proposal. Buys have zero modeled SEC/TAF sell fees.

| Start date | SEC dollars / million | Official advisory |
|---|---:|---|
| 2016-01-01 (support boundary) | 18.40 | [FY2016 carry-forward](https://www.sec.gov/news/pressrelease/2015-222.html) |
| 2016-02-16 | 21.80 | [FY2016](https://www.sec.gov/news/pressrelease/2016-2.html) |
| 2017-07-04 | 23.10 | [FY2017](https://www.sec.gov/newsroom/press-releases/2017-111) |
| 2018-05-22 | 13.00 | [FY2018](https://www.sec.gov/newsroom/press-releases/2018-67) |
| 2019-04-16 | 20.70 | [FY2019](https://www.sec.gov/newsroom/press-releases/2019-30) |
| 2020-02-18 | 22.10 | [FY2020](https://www.sec.gov/newsroom/press-releases/2020-7) |
| 2021-02-25 | 5.10 | [FY2021](https://www.sec.gov/newsroom/press-releases/2021-8) |
| 2022-05-14 | 22.90 | [FY2022](https://www.sec.gov/newsroom/press-releases/2022-60) |
| 2023-02-27 | 8.00 | [FY2023](https://www.sec.gov/newsroom/press-releases/2023-15) |
| 2024-05-22 | 27.80 | [FY2024](https://www.sec.gov/rules-regulations/fee-rate-advisories/2024-2) |
| 2025-05-14 | 0.00 | [FY2025](https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2) |
| 2026-04-04 | 20.60 | [FY2026](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2) |

FINRA equity TAF: 2016–2021 $0.000119/share capped $5.95; 2022 $0.000130/$6.49;
2023 $0.000145/$7.27; 2024–2025 $0.000166/$8.30. The
[immediately effective 2020 filing](https://www.finra.org/sites/default/files/2020-10/NOF%20IMM%20EFF%20FINRA-2020-032.pdf)
provides the old rate, phased table (page 6) and January 1, 2022 implementation
(page 8). The [2012 rule text](https://www.finra.org/sites/default/files/RuleFiling/p179403.pdf)
corroborates the earlier equity rate and below-rate execution-price exemption.
For 2026, $0.000195/share capped $9.79 follows the
[FINRA implementation schedule](https://www.finra.org/rules-guidance/rule-filings/sr-finra-2024-019/fee-adjustment-schedule).
TAF is zero when execution price is below the per-share rate.

## Verification and adoption

Run `.venv/bin/python -m unittest test_intraday_costs -q`. Boundary tests cover
legacy preservation, provenance corruption, missing coverage, nonfinite inputs,
causal quote filtering, volume availability, capacity, market calendar, fee date
changes/caps and explicit raw inputs. Independent reviewer records acceptance in
a separate audit. **Tenzing signature/date: pending.** No strategy verdict,
Phase 2 adoption or order authorization follows from passing these tests.
