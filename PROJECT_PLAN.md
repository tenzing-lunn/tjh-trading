# 🧭 Algo-Trading Club — Home (Map of Content)

*This is the front door. It links to everything. Start here when you sit down to work.*
*Tenzing's project, ~$3–5k of his own money, run with Claude subagents. Two equal goals: learn
enough to put real work on his résumé, and grow the money without doing anything stupid.*

Last touched: 2026-09-16. Resumed the intraday/swing plan from the September 15
handoff. The data-admission corrections passed independent boundary
verification; the next deliverable is a reviewed, unsigned I1.5 execution-cost
proposal. See [[plan/14-intraday-plan]], [[plan/16-agent-routing]] and `HANDOFF.md`.
The older web-app/universe milestones remain recorded in [[plan/01-decision-log]].

---

## ⛔ The non-negotiables (read every time — these override enthusiasm)

1. **A strategy is only real if it beats buy-and-hold AND random, out-of-sample, after
   costs.** The only number that isn't lying is the OOS walk-forward row, net of `costs.py`,
   on **real** data. Everything else is diagnosis.
2. **Money is separate from software.** Capital stays indexed or paper-traded until a
   strategy clears #1. We build the algo; we don't *fund* it on hope.
3. **Options are paper-only for now.** We model and visualize options (see [[webapp/SPEC]]),
   but no real options money until a strategy survives #1 *in the cheap-option cost regime*.
   Our own harness sends naive options strategies to ~−100%. Respect that.
4. **No outside money, ever, in the current structure.** This is Tenzing's own money, run with
   Claude subagents. The Fordham-club ambition is *education/research*, not pooling strangers'
   capital. See [[plan/00-vision]].
5. **Honesty is the asset.** "We tested 10 things and 9 had no edge" is a *stronger* résumé
   and a better club than one fake winner. The logs do not get edited to flatter us.

---

## 🗂️ The knowledge base

### plan/ — the thinking
- [[plan/00-vision]] — north star, the Fordham-club endgame, principles, résumé payoff
- [[plan/01-decision-log]] — every meaningful/irreversible decision, with the *why*. **Keep current.**
- [[plan/02-verdict-log]] — the research track record: what we tested, OOS-net-of-costs vs SPY. **The asset.**
- [[plan/03-roadmap]] — Now / Next / Later (no dates — we move as fast as we can)
- [[plan/04-glossary]] — terms (OOS, walk-forward, theta, IV, Greeks…) so nobody's lost
- [[plan/05-risk-register]] — what could blow us up (legal, capital, model self-deception)
- [[plan/06-engineering-plan]] — Tenzing's coding roadmap: deployed app first, future system captured
- [[plan/07-charter-what-we-do]] — **what we're doing / NOT doing** (goal, scope, stack). Read cold here.
- [[plan/08-alpaca-setup]] — shared paper account + data→research→paper loop
- [[plan/09-status-where-we-are]] — **living status tracker** (8-stage pipeline, current bottleneck). Read FIRST.
- [[plan/10-verdict-and-diagnostics-spec]] — build spec: verdict auto-logger + robustness/red-flag diagnostics
- [[plan/11-strategy-pipeline]] — **how we find/test/run/show strategies** (the merged scan→gate design)
- [[plan/12-real-markets-plan]] — **what's missing for real markets** (2026-09-13): proof → paper plumbing → risk → taxes, each task assigned to a Claude model by difficulty, humans own the gates
- [[plan/14-intraday-plan]] — **short-term scope** (2026-09-14): intraday + swing on free Alpaca SIP minute bars with the 15-min delay simulated; adopts the IQF document's data-quality / ledger / risk-gate / AI-authority ideas; three-way verdicts

### roles/ — who does what
- [[roles/ROLE_Tenzing]] — engineering / the machine
- [[roles/standup-template]] — the recurring update routine (copy per work cycle)
- [[roles/log-Tenzing]] — rolling personal log (`roles/archive/` holds the retired
  role and log files)

### research/ — the ideas
- [[research/_thesis-template]] — copy this for every strategy idea
- `research/theses/` — one file per hypothesis we test
  - [[research/theses/001-cross-sectional-momentum]] — Thesis 001, **UNPROVEN** (2026-09-14:
    the edge over EW-universe is not statistically distinguishable from luck, t=0.34),
    **pending Tenzing's signature**

### notion-import/ — the beginner-friendly front door (2026-07-06)
A ready-to-import Notion workspace structure, written for people new to Notion or this repo.
Plain-English rewrites of the plan/roles/research pages above — Notion is the summary + to-do
front door, this repo stays the detailed source of truth. See `notion-import/HOW_TO_IMPORT.md`
for the one-time import steps. Replaces whatever existed in Notion before (see
[[plan/01-decision-log]] 2026-07-06 for why it needed restructuring).

### webapp/ — what we're building
- [[webapp/SPEC]] — the prediction-vs-actual + cost-simulation visualizer
- [[webapp/DESIGN_TARGET]] — the 5-panel visual target Claude CLI builds to
- `webapp/MOCKUP.html` — the actual mockup (open in a browser; this is the look we want)
- [[webapp/options-modeling]] — how we model options honestly, and what we're missing

### The machine (canonical source of truth)
The `.py` files (`costs.py`, `backtest.py`, `walkforward.py`, `strategies.py`, `data.py`,
`forecast_kronos.py`, `run.py`) + Obsidian notes [[Backtest]], [[Costs]], [[Run]].
See the repo `CLAUDE.md` for how the engine works and its invariants.

---

## 🔁 How this doc stays alive
This is a *living* plan. The rule: **when a work session changes a decision, a role, or the
roadmap, it gets written down the same session** — in [[plan/01-decision-log]] and the
affected file — and Claude updates its cloud memory so the next session starts current.
Stale plan = dead plan.

## ▶️ Current focus
Agent execution follows [[plan/16-agent-routing]]: specialized implementers and a
separate orchestrator-verifier, with actual available models recorded explicitly.
Short-term intraday/swing research under [[plan/14-intraday-plan]]. Updated 2026-09-16:
Phase 0, the minute fetcher and spread measurements are complete. Data-admission
fixes have passed independent review. The I1.5 execution-cost proposal is being
prepared for Tenzing to sign before adoption, followed by the session/delay
engine and independent audit. The current daily scan still has zero edges;
Thesis 001 remains INCONCLUSIVE and parked. See [[plan/03-roadmap]].
