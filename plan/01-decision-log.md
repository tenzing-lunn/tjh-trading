# 01 — Decision Log

Home: [[PROJECT_PLAN]]

*Every meaningful or hard-to-reverse decision goes here, newest first. Format: date —
decision — why — who. This is how we remember why we did things and avoid relitigating them.
When a decision changes, add a NEW entry that supersedes the old one (don't delete history).*

---

### 2026-09-15 — Specialized implementers and an independent orchestrator-verifier
**Instruction:** Tenzing requires following the plan's division of work by model,
with an orchestrator-verifier agent. Direct implementation followed only by the
same assistant's checks does not satisfy this workflow.
**Codex execution mapping:** Fable role → GPT-6 Astra; Opus role → GPT-5.6 Sol;
Sonnet role → GPT-5.6 Terra; Haiku role → GPT-5.6 Luna. The named Claude models
are unavailable through this session's agent tool. These are explicit role
substitutions, not claims of model equivalence; original task assignments remain.
**Process:** bounded file ownership, distinct implementer/reviewer models,
independent reproduction before acceptance, and Tenzing's existing human gates.
The retrospective review already reopened two I1.2 admission checks; the earlier
completion entry below is an implementation checkpoint, not an independent audit.
**Who:** Tenzing (workflow instruction); Codex (available-model routing).
**Reference:** [[plan/16-agent-routing]].

### 2026-09-15 — Data admission and spread sampling implemented
**Implementation decisions under plan/14:** intraday admission uses exchange-calendar
symbol-days and SHA-256-bound quality reports; daily CSV admission validates at load.
Minute sessions stay separate so exclusions cannot silently compress trading time.
For I1.4, the initial one-second samples left 5,250 no-update observations. A fixed
60-second backward lookup, clamped to the same bucket, recovered missing quotes at
unchanged sample timestamps. Existing valid/locked/crossed observations were retained.
Final coverage is 21,094/21,120 valid. This changes measurement completeness, not a
strategy selection rule; no new strategy variants were tested. Validation reruns used
`LEDGER_DISABLE=1` and left both ledgers unchanged.
**Finding:** SPY midday half-spread is 0.170 bps, below the rough planning estimate.
Keep the measurements; do not force them to match an expectation. These are quotes,
not fills. Existing cost constants remain unchanged; Tenzing still owns I1.5 sign-off.
**Who:** Codex, implementing Tenzing's instruction to continue the approved plan.
**Evidence:** [[research/audits/intraday-data]], [[Costs]], [[plan/14-intraday-plan]].

### 2026-09-14 — Jonathan and Henry are no longer part of this project; Tenzing runs it with Claude subagents
**Decision:** Jonathan and Henry are subtracted from the idea of the project — they never
produced theses, so their work is not being run. This is now Tenzing's project, run with
Claude subagents (the model roster in [[plan/12-real-markets-plan]]: Fable 5.1 for audits,
Opus 5 for the core engine, Sonnet 5 for features/docs, Haiku 4.5 for simple tasks). Every
human gate/sign-off previously written as "Tenzing + Jonathan + Henry," "Jonathan signs,"
"Henry signs," "Jonathan writes the thesis," or "Henry checks costs / logs verdicts" is now
**Tenzing** — theses are written by Tenzing with Claude, pre-registered before results are
seen, and the Fable audit remains the independent check. "The three of us" becomes Tenzing.
This entry **supersedes the roles/ratification parts** of every earlier decision below (e.g.
"to be ratified with Jonathan & Henry," "pending Jonathan's signature," "Henry to ratify," and
the "Jonathan and Henry to ratify at G2" line in the entry immediately below) — the underlying
engineering/research decisions themselves stand unchanged. Their old role and log files are
archived, not deleted, at `roles/archive/` and `notion-import/02 - Roles/archive/`.
**Why:** Neither ever produced a strategy thesis or a cost/universe ratification in the roles
they were assigned; carrying two placeholder human gates that never fire was blocking the
pipeline for no reason. Tenzing, directing Claude subagents (with Fable's audits as the
independent check this project always required), can own both the offense and the reality-check
roles directly.
**Who:** Tenzing, 2026-09-14.

### 2026-09-14 — Scope moves to short-term (intraday + swing); 15-minute delay simulated, realtime feed deferred
**Decision:** Strategy horizon is now **minutes → ~2 weeks**. Intraday is in scope, which
supersedes the 2026-07-02 "park Kronos" decision. Data source: Alpaca's free SIP minute bars
(2016→now, adjusted, verified with our keys 2026-09-14). We do **not** buy the ~$99/mo
realtime SIP feed yet; every intraday test bakes the free plan's 15-minute delay into the
engine, and the purchase is proposed only for a strategy that passes with it. From the
"Integrated Quant Framework" document we adopt: fail-closed data quality, point-in-time
timestamps, an experiment ledger, the backtest→replay→shadow→paper ladder, a risk gate outside
the strategy, and — as the stated end goal — an AI layer that can execute on its own under a
signed authority ladder it cannot modify. We reject signal-fusion, QUANTAXIS and OpenBB (for
now), and skip Kafka/Prometheus/Kubernetes. Full plan: [[plan/14-intraday-plan]].
**Also:** the panel verdict becomes three-way (PASS / FAIL / INCONCLUSIVE) with a power check;
momentum's Gate G1 criterion 2 is restated as INCONCLUSIVE, not FAIL.
**Why:** Phase 1 of plan/12 showed a monthly strategy can't reach t ≥ 2 on 7–17 years of data
even if real (27–149 years needed). Daily-or-faster bets gather evidence ~20× faster. The
charter already said swing; intraday is the deliberate scope change, now made.
**Who:** Tenzing (Claude briefed the tradeoffs); Jonathan and Henry to ratify at G2.

### 2026-09-13 — Thesis 001 downgraded to unproven; new real-markets plan with model-assigned tasks
**Decision:** Stop treating Thesis 001 as a survivor awaiting sign-off. Pause the sign-off →
paper-trade path. Follow [[plan/12-real-markets-plan]] instead: Phase 0 (fix the gate) and
Phase 1 (long-history, no-hindsight and MTUM tests), then a human go/no-go gate (G1) with
criteria written *before* the results. Each task is assigned a Claude model by difficulty:
Fable 5.1 for method design and audits, Opus 5 for engine and money-adjacent code, Sonnet 5 for
routine builds, Haiku 4.5 for mechanical work. Humans own every gate; agents never place orders.
**Why:** a direct significance test of momentum's monthly extra return over EW-universe gave
t = 0.34 on the 30-name core (won 48% of months; loses ex-NVDA). On the archived larger universe
it gave t = 1.65, driven by PLUG/AMD/NIO (t = 0.72 without them). The old "PSR 1.00" gate
measured P(Sharpe > 0), not P(beats EW), so it overstated the edge. See [[plan/02-verdict-log]]
2026-09-13.
**Also proposed (needs team decision):** replace "paper-trade 2+ weeks" with **≥3 monthly
rebalances**. With monthly rebalancing, 2 weeks tests nothing.
**Who:** Tenzing (directed Claude), 2026-09-13. Jonathan and Henry to review the G1 criteria.

### 2026-07-06 — Universe slimmed 97 → 30: quality over quantity, and the engine re-run live to prove it
**Decision:** Cut the working universe (`realdata/`, `fetch_universe.py`) from ~97 liquid names
down to a deliberately small, boring, diversified core of **30 megacaps across 6 sectors**
(tech, financials, healthcare, consumer, energy/industrial), plus SPY as the lone benchmark.
Cut: all penny/pre-IPO/speculative names (nio, sofi, plug, snap), the leveraged ETF (tqqq),
and redundant index ETFs (qqq, dia, iwm, vti). The archived ~97-name data (72 CSVs) is kept,
untouched, in `realdata_archive_97/` (gitignored, not deleted) so we can restore or re-widen
later without re-fetching from Yahoo.
**Why:** 100 names is more than a 3-person club needs to prototype and reason about, and a
bigger haystack just buries the signal in more noise (more multiple-testing burden for the
same conclusion). A small, high-quality, explainable universe is easier to defend to Jonathan/
Henry and is exactly the kind of list Henry's charter role (ratify the tradable universe) is
supposed to bless — this is Tenzing's proposal for that list, not yet Henry's ratification.
**Result of re-running the engine live on the new 30-name universe (2026-07-06):**
- `xsect.py` (Thesis 001, cross-sectional 12-1 momentum): momentum top-10 **+309.4%** vs EW
  universe **+284.5%** vs random top-10 **+276.5%** vs hold SPY **+179.7%**, 2019-08→2026-07.
  Still beats all three bars on raw return; monthly probabilistic Sharpe still **1.00**
  ~~; sensitivity sweep **7/9** neighbors beat EW (vs 9/9 on the ~97 universe — a bit less
  broad, still solid)~~ (superseded 2026-09-13/14: PSR 1.00 is P(Sharpe>0), which every
  baseline also scores ~1.00 on; the sweep's real significance count is 0/9 at t≥2, not
  "7/9 beat EW" — see [[research/theses/001-cross-sectional-momentum]]); chop
  red flag improved to −22.4% (was −39.1% on the larger universe). The absolute numbers moved
  a lot (+972% → +309%) because it's a materially different, smaller universe — **this is a
  robustness cross-check on an independently different universe, not a restatement of the
  original ~97-name result**, and both are logged (see [[plan/02-verdict-log]]).
- `scan.py` (wide single-name scan): 31 tickers × 3 strategies = 93 backtests → **0 EDGE?, 10
  suspect, 83 dead**. Same honest base rate as the ~100-name run (0/309), just cheaper to run
  and easier to read (93 rows, not 309).
**Who:** Tenzing (directed Claude), 2026-07-06. Still needs Henry's formal ratification of the
30-name list per his role (real cost table + tradable universe).

### 2026-07-06 — Notion restructured into a beginner-friendly front door (`notion-import/`)
**Decision:** The Notion workspace had grown disorganized, and neither Jonathan nor Henry (nor
Tenzing) has real Notion experience. Rather than reorganize an existing Notion workspace by
hand (no Notion API/MCP access available from this environment), built a complete replacement
structure as `notion-import/` in the repo: 8 top-level pages (Start Here, What To Do Right Now,
Roles, Strategy Ideas, Results So Far, Roadmap, Glossary, Decisions We've Made) written in
plain English, ready to import via Notion's Markdown & CSV importer (`HOW_TO_IMPORT.md` has
the exact steps). Content is a beginner-friendly distillation of `plan/`, `roles/`, and
`research/` — those stay canonical and more detailed; Notion is the summary/to-do front door.
**Why:** A disorganized workspace nobody can navigate doesn't get used, and Jonathan/Henry's
outstanding sign-offs (the actual bottleneck — see [[plan/09-status-where-we-are]]) are more
likely to happen if the ask is legible in 2 minutes, not buried in stale pages.
**Who:** Tenzing (directed Claude), 2026-07-06.

### 2026-07-06 — Repo/plan hygiene pass: dead code removed, stale docs refreshed, Thesis 001 doc written
**Decision:** A full review of unfinished workflows and plan-layer staleness surfaced (1) real
process gaps and (2) repo clutter. Fixed the clutter same-session per the maintenance rule:
- Deleted `dashboard.py` + `dashboard_template.py` — an abandoned first-commit prototype
  (single-file HTML dashboard) never listed in CLAUDE.md's canonical files table and fully
  superseded by `export_results.py`/`api_server.py`/the Next.js app.
- Deleted the `feat/webapp-v1` branch (local + remote) — fully fast-forward-merged to `main`
  on 2026-07-02 (verified zero unique commits), left over in violation of the "no long-lived
  feature branches" rule.
- Refreshed `plan/03-roadmap.md`, which was stale (last touched 2026-07-02, described
  already-shipped work as "Next"). Now points at the real bottleneck: human sign-offs
  (Jonathan, Henry) and two small engineering loose ends (empty Alpaca `.env` keys;
  `scan.py`/`xsect.py` results not wired into `verdict_log.py`'s auto-logger, so
  `verdicts.jsonl` is missing the wide-scan-v3 and Thesis-001 runs — only 2 stale
  `run.py`-only rows exist).
- Updated `Run.md`'s embedded code block, which had drifted from `run.py` since 2026-07-02
  (missing the Kronos row + verdict auto-logger it gained that session).
- Wrote `research/theses/001-cross-sectional-momentum.md` — Thesis 001 had been implemented,
  run, and referenced everywhere in the plan layer, but no actual thesis file existed for
  Jonathan to sign (the file this project's own process requires). Backfilled from the real
  `xsect.py`/`diagnostics.py` output so his signature means something concrete.
**Why:** "Stale plan = dead plan," and dead branches/files erode trust in what's canonical.
None of this changes engine logic or any verdict — pure hygiene plus closing a process gap.
**Who:** Tenzing (directed Claude, full-project review, 2026-07-06).

### 2026-07-03 — Thesis 001 engine mismatch resolved: built the panel engine and ran it
**Decision:** Thesis 001 (cross-sectional 12-1 momentum) as drafted could NOT run on the
single-ticker engine — a gap discovered 2026-07-03. Resolved by building it, in two steps:
(1) `time_series_momentum` added to the single-name library and scanned (159 backtests,
0 clean edges, but tsmom the strongest suspect family — the "hint" that justified step 2);
(2) `xsect.py`, a cross-sectional panel engine (same shift(1) no-lookahead, same cost model,
judged vs EW-universe + random picks + SPY). ~~Thesis 001 **survives its first panel
test**~~ (superseded 2026-09-13: UNPROVEN, t=0.34 — see [[research/theses/001-cross-sectional-momentum]])
(see [[plan/02-verdict-log]]). The run happened before Jonathan's signature in order to
resolve the mismatch and produce evidence; his sign-off (and Henry's judgment) is still
REQUIRED before any ADVANCE to paper trading — the ownership rule stands, the sequencing
was pragmatic.
**Why:** we were asking Jonathan to sign a strategy the machine couldn't execute.
**Who:** Tenzing (directed Claude, 2026-07-03).

### 2026-07-03 — Web app v2: real data by default, real track record on the page, mockup styling
**Decision:** The deployed app no longer opens on the synthetic fixture. It defaults to
live SPY (synthetic is a clearly-labelled fallback/demo), is restyled to `webapp/MOCKUP.html`,
and renders the club's actual research record (wide scan + Thesis 001) from
`webapp/lib/track_record.json` — generated by `export_track_record.py` from the same engines
that produced the verdicts, and committed so the record shows even when the free backend sleeps.
**Why:** Tenzing's verdict on v1: "this doesn't do much for us right now" — a synthetic demo
that flatters itself is not evidence of work. The record is.
**Who:** Tenzing.

### 2026-07-02 — Park Kronos; it's intraday-strongest and we trade daily swing
**Decision:** Stop treating a real Kronos run as a near-term action. Kronos (zero-shot,
`forecast_kronos.py`) is strongest on **intraday** bars; our locked strategy style is
**daily swing** (charter [[plan/07-charter-what-we-do]]). Running it zero-shot on daily bars
is an expected "no edge" that answers a question we don't need answered, so it drops below
Jonathan's thesis in priority. **Revisit only** if we deliberately choose to go intraday
(a phase-2 scope change not yet made). The alignment fix and plumbing stay in the repo so the
run is one command away if that decision flips.
**Why:** Tenzing flagged the timeframe mismatch — spending a torch install + an evening on a
tool mismatched to our horizon is low-value work. Supersedes the "run Kronos for real" framing
in the 2026-06-27 "zero-shot Kronos first" decision (that decision still holds *if* we go intraday).
**Who:** Tenzing.

### 2026-07-02 — Web app frontend deployed to Vercel (production)
**Decision:** The Next.js visualizer is live at https://webapp-zeta-liart.vercel.app (deployed
from the `webapp/` root, not the repo root). It is a **shell until the backend is hosted** —
`api_server.py` (FastAPI) can't run on Vercel, so it goes on a Python host (`render.yaml`
blueprint added for Render's free tier), and the Vercel env var `NEXT_PUBLIC_API_URL` points
the frontend at it. No backtest math ever runs in the browser.
**Why:** The deployed URL is the engagement unlock for Jonathan & Henry (they judge realness by
a live app). Engine work was gated first and is now done, so deploy was the next move.
**Who:** Tenzing.

### 2026-07-02 — Work merges to `main` the same session it stops; `main` is the only truth
**Decision:** No long-lived feature branches. Whatever is done at the end of a work session
gets merged to `main` and pushed. Status pages (Notion, plan/09) are always written from `main`.
**Why:** All real work Jun 29–Jul 1 sat only on `feat/webapp-v1` while `main` looked 3 weeks
stale — the Jul 2 Notion status was accidentally written from `main` and reported finished work
(web app, data cleanup, universe, diagnostics) as not started. Two sources of truth = zero.
Merged (clean fast-forward) 2026-07-02.
**Who:** Tenzing (Claude flagged it during the full-project review).

### 2026-06-30 — Automate verdict capture; Henry owns judgment, not clerical logging
**Decision:** The mechanical verdict row (strategy, params, OOS-net-of-costs, vs-SPY benchmark,
date) gets auto-appended by the harness (extend `run.py`/`export_results.py` to write a
machine-readable `verdicts.jsonl`, render the human log from it). Henry no longer hand-copies
numbers. His reframed deliverable: the *interpretation* a machine can't do — is it real or luck,
regime dependence, suspicious trade counts, selection bias, advance-or-kill.
**Why:** Tenzing correctly flagged that logging is already produced in code; making a person
retype it is wasted effort and error-prone. Automate the capture, keep the human on judgment.
**Status:** auto-logger not built yet (tracked in [[plan/09-status-where-we-are]]); role doc
[[roles/ROLE_Henry]] updated.
**Who:** Tenzing (proposed); Henry to confirm the reframe.

### 2026-06-30 — Phase-1 scope locked: equities-first, swing-style, Alpaca paper, cash parked
**Decision:** Charter written in [[plan/07-charter-what-we-do]]. Phase-1 goal = find ONE signal
that beats buy-and-hold OOS net of costs on real equity data (we have zero). We trade liquid US
equities/ETFs first, swing-style (daily bars, hold days–weeks), paper-traded on **Alpaca** (free
paper API). The $3–5k stays in an index fund until something clears the bar.
**Also decided:** NOT day-trading small caps; NOT chasing strategy quantity (multiple-testing
trap); shared Alpaca **paper** account via API keys is fine, but NO pooling into one live
brokerage account (same securities-law issue as the killed "outside money" idea — real-money
structure deferred). Never generate price data with an LLM.
**Why:** Tenzing was carrying all the work and the team lacked a shared definition of the goal,
the instrument, and the stack. This gives Jonathan (first thesis) and Henry (cost table +
universe + verdict log) concrete next deliverables.
**Reference (verified 2026-06-30):** PDT $25k minimum eliminated 2026-06-04, replaced by
intraday margin standards ($2k min equity) — removes a legal barrier, not the difficulty.
Alpaca hidden cost = free data is IEX-only; full SIP feed ~$99/mo (paper/daily backtest free).
**Who:** Tenzing (Claude grilled the goal/stack); to be ratified with Jonathan & Henry.

### 2026-06-29 — Web app v1 = Next.js front end + a Python harness API (run on demand)
**Decision:** Build the visualizer as two services: a Next.js/Vercel front end and a FastAPI
backend (`api_server.py`) that runs the canonical harness on demand, so users can pick any
ticker and tweak cost assumptions live and see the result recomputed. The API reuses the exact
`export_results` code path the CLI uses, so the app and the offline numbers cannot drift.
**Why:** Chose the "fully done" architecture over a quick static bundle — live ticker choice +
cost tweaking is the whole point of the teaching tool, and the backend is real system-design
reps (Tenzing's learning goal). Trade-off acknowledged: more infra than a static site, so we
guard against scope creep (risk register) by shipping a working vertical slice first.
**Guardrails:** Python produces truth; no backtest math in JS; no order execution; vendor
price data stays out of public commits. Supersedes the implicit "static, no backend" framing.
**Who:** Tenzing (chose B over a static-only v1).

### 2026-06-27 — Options are paper-only until proven in the cheap-option cost regime
**Decision:** We may *model and visualize* options in the web app, but no real capital goes
into options until a strategy survives walk-forward OOS net of costs in the 300/50 bps
"cheap option" regime.
**Why:** Our own harness sends naive options strategies to ~−100%. Being right on direction
still loses to theta + wide spreads. Beginners + options + real money = fastest path to zero.
**Who:** Tenzing (Claude grilled it).

### 2026-06-27 — Build a visualizer web app as the current focus
**Decision:** Build a web app that overlays model predictions vs actual price and simulates
"pay-per-trade" P&L net of costs, with live quotes for display. See [[webapp/SPEC]].
**Why:** It's the portfolio centerpiece, drives Tenzing's Supabase/Vercel learning, and makes
results legible to the finance two. Options modeling here is zero-capital-risk.
**Who:** Tenzing.

### 2026-06-27 — Kill the "platform for outside money" idea; pursue a Fordham research club instead
**Decision:** No app where strangers deposit money for us to manage. Long-term ambition is a
*research/education* club at Fordham.
**Why:** Pooling/managing outsiders' money = unregistered investment vehicle / securities
law. A research club has no such exposure and is better for résumés. See [[plan/05-risk-register]].
**Who:** All three (idea originated loosely; formalized here).

### 2026-06-27 — Operate as an investment club; money separate from software
**Decision:** Three of us, own money, equal say, P&L split by contribution. Capital stays
indexed/paper-traded until a strategy clears the OOS-net-of-costs bar.
**Why:** Legal, simple, résumé-legible. Avoids funding unproven strategies.
**Who:** All three.

### 2026-06-27 — Zero-shot Kronos first; finetune only if it shows OOS edge
**Decision:** Run Kronos zero-shot on real data before investing in finetuning (Qlib,
multi-GPU).
**Why:** Don't pay the cost of finetuning until the cheap version shows a non-trivial edge.
**Who:** Tenzing (from project history).
