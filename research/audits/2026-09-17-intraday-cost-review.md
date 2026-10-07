# I1.5 independent review — 2026-09-17

Reviewer: `cost_review`, a separate agent inheriting this Codex/GPT-6 session.
The exact model alias is not exposed to this reviewer; this is separate-agent
verification, not a claim of distinct-model Astra/Sol review. The reviewer edited
only this audit. Findings were returned to `cost_completion` for fixes.

Status: final proposal and artifact verification pending. Human adoption remains
separate and unsigned.

## Reproduced defects and corrections

- The original test helper eagerly rewrote supplied fixture artifacts. Two of ten
  tests failed; the low-coverage fixture also used an out-of-session UTC time.
  The implementer corrected fixture construction and timestamps.
- The original clock-only buckets accepted Sunday, July 4, and an execution after
  the November 29, 2024 early close. The implementation now checks the shared
  exchange calendar and refuses every early-close session because its spread
  calibration is for full sessions. Independent probes also reject the January
  9, 2025 Carter mourning closure.
- Positive finite share/price inputs could multiply to zero and raise division by
  zero; very small sell notionals could produce infinite cost bps. Independent
  reproductions now receive explicit `ValueError` refusals.

## Methodology boundaries

The causal spread filter excludes same-day and future **values**, and coverage
uses only the eligible prior sampling windows. The historical sampling plan was
constructed retrospectively: this does not establish fully point-in-time sample
selection. Full-current-bar volume is refused in causal mode; asserted prior
volume must have an availability timestamp no later than the order. Raw shares,
price and volume require explicit confirmation. These assertions cannot prove
the upstream data were actually raw or available; the future engine must preserve
that provenance. The legacy bar-only engine refuses this model's API.

The coefficient is a conservative policy proposal, not an empirical fill model.
Sparse quote snapshots cannot establish realized execution, queue position, or
market impact. Rounding is an explicit modeling convention, not proof of a
broker's actual bill. No order or ledger entry was created by this review.

## Independent source checks

- [SEC 2026 Section 31 advisory](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2)
  confirms $20.60 per million from April 4, 2026.
- [SEC 2016 advisory](https://www.sec.gov/newsroom/press-releases/2016-2)
  confirms $18.40 before February 16 and $21.80 from that date.
- [FINRA 2020 fee filing](https://www.finra.org/sites/default/files/2020-10/SR-FINRA-2020-032.pdf)
  supplies the 2022–2024 share rates/caps used here.
- [FINRA 2024 fee filing](https://www.finra.org/sites/default/files/2024-11/sr-finra-2024-019.pdf)
  supplies the 2026 $0.000195/share and $9.79 cap, and describes the low-price
  exemption. [FINRA Schedule A](https://www.finra.org/rules-guidance/rulebooks/corporate-organization/section-1-member-regulatory-fees)
  identifies covered equity sales as the assessed activity.

These checks corroborate the stated schedules; they do not turn unsigned
slippage constants into measured facts.
