# 16 — Agent routing and independent verification

Home: [[PROJECT_PLAN]] · Work: [[plan/14-intraday-plan]]

## User instruction — 2026-09-15

Tenzing explicitly requires task-specific model assignments and an
orchestrator-verifier agent. The original Claude role assignments in plan/12 and
plan/14 remain the design intent. Those named Claude models are not selectable
through this Codex session's agent tool; the table below records the actual
available-model substitutions rather than claiming Claude agents were launched.

| Planned role | Available model used | Scope |
|---|---|---|
| Fable: methodology and adversarial audit | GPT-6 Astra | Independent review, evidence checks, dependency readiness and acceptance recommendations |
| Opus: core engineering | GPT-5.6 Sol | Cost models, data-admission corrections, engine timing/accounting and statistical implementation |
| Sonnet: defined features | GPT-5.6 Terra | Clearly specified scripts, tests, UI and documentation requiring judgment |
| Haiku: mechanical work | GPT-5.6 Luna | Bounded data inventories, formatting, link checks and existing-command checks |

This is a practical routing policy based on the available models' stated roles,
not a measured equivalence between model families. Escalate uncertain reasoning
and failed reviews to the verifier. Do not assign statistical design or safety
logic to the mechanical tier to save effort.

## Execution rules

1. Root coordinates task scope, ownership and integration. It does not replace
   assigned implementers with unrecorded direct implementation.
2. Each agent gets a bounded task, prerequisites, permitted files, acceptance
   checks and actual model identity. Use separate worktrees for overlapping
   edits; disjoint files may share the checkout with explicit ownership.
3. The orchestrator-verifier checks prerequisites and independently reproduces
   claims. An implementer cannot approve its own task. New Sol implementations
   are reviewed by a separate Astra agent with fresh context.
4. Passing existing tests is evidence, not automatic acceptance. The verifier
   also checks omitted requirements and adversarial cases. Findings go back to
   an implementer, followed by independent re-verification.
5. Mark implementation, independent verification and human sign-off separately.
   Earlier completed checkboxes do not imply an independent model audit occurred.
   The retrospective review of `20e7c73` is an interim data review, not I2.6.
6. Preserve plan dependencies, no-lookahead, cost accounting and ledger hygiene.
   No orders or paid services. Tenzing retains every human gate, including I1.5
   constants. Drafting and testing unsigned code is permitted; adoption is not.

## Prior checkpoint — 2026-09-16

Prior-session agents are not assumed to still be running. This session resumes
from the saved working-tree corrections and the September 15 audit.

| Agent | Model | Task | State |
|---|---|---|---|
| `data_verifier` | GPT-6 Astra, high reasoning | Independently verify saved I1.2 fixes, boundary cases and real daily admission | Accepted; audit saved |
| `data_boundary_fix` | GPT-5.6 Sol, high reasoning | Correct exact-60% daily threshold rounding and add regression cases | Implemented; independently accepted |
| `cost_implementation` | GPT-5.6 Sol, high reasoning | I1.5 opt-in implementation, tests and sourced unsigned cost proposal | Interrupted; saved draft resumed September 17 |
| `cost_verifier` | GPT-6 Astra, high reasoning | Independently review I1.5 sources, calculations and refusal behavior | No completed audit saved; resumed September 17 |

The data verifier owns only `research/audits/2026-09-16-data-fix-verification.md`.
The cost implementer owns `costs.py`, `test_intraday_costs.py`,
`research/intraday-cost-proposal.md` and the matching `Costs.md` note. Root
maintains the task register and plan/handoff. The separate cost reviewer owns only
`research/audits/2026-09-16-intraday-cost-review.md` and checks the completed
cost draft before it is presented for human adoption.

The saved I1.2 corrections address missing enforcement of the >3-session
intraday gap rule and missing daily absurd-jump screening. Independent acceptance is complete: 21 data-suite tests plus adversarial
fixtures pass, all 31 daily files load and the 93-row scan headline is unchanged.
See [[research/audits/2026-09-16-data-fix-verification]]. Separate point-in-time loader
repairs remain open; the earlier review reproduced WRK/PARA/TMUS/SW corruption
in that parked pipeline. I1.4 quote arithmetic was independently reproduced,
with limitations for sparse annual samples and historical cost calibration.

## Current continuation — 2026-09-17

The user requested completion of the saved plan. Root recovered the unfinished
I1.5 implementation; the proposal and cost audit were absent. Initial validation
ran 31 tests with two failures caused by test fixtures being overwritten during
model construction; an additional coverage-test timestamp was outside market hours.

Separate `cost_completion` and `cost_review` agents now own implementation and
independent review respectively. Both use the session's inherited model; the
earlier Sol/Astra routing is **not** claimed for this continuation. This provides
separate-agent review, not the distinct-model verification previously requested.
The implementation owns `costs.py`, `test_intraday_costs.py`,
`research/intraday-cost-proposal.md`, and `Costs.md`. The reviewer owns
`research/audits/2026-09-17-intraday-cost-review.md`. Root owns plan/handoff
integration and regression verification. No I1.5 constants are adopted by this
continuation; the existing human signature gate remains pending.
