# algo-trading — Backtest Harness ("the skeptic's machine")

Context + memory file for this folder. Read this first when working here.

## What this is
A small, honest backtesting pipeline that evaluates trading strategies **net of
realistic costs** with **walk-forward (out-of-sample)** validation. Designed to
*disprove* strategies, not flatter them. Stated goal: turn $23 into more — but the
real deliverable is a machine that tells the truth about whether an edge exists.

**The one rule:** a strategy is only "real" if it beats dumb baselines
(buy-and-hold, random) out-of-sample, after costs. Almost nothing does. That's the point.

## Canonical files (the `.py` are the source of truth)
| File | Job |
|------|-----|
| `costs.py` | Cost model (spread + slippage + fee, in bps). **Most important file.** A strategy is only real if it survives this. |
| `backtest.py` | Bar-by-bar engine. Enforces no-lookahead via `held = positions.shift(1)`. |
| `metrics.py` | Sharpe, max DD, win rate, trades, EV/trade. Recomputes equity per slice → safe on walk-forward folds. |
| `strategies.py` | Signals returning a position Series in [-1,1]: buy&hold, random, SMA crossover, mean-reversion (z-score), **kronos_signal** (reads a cached forecast). |
| `walkforward.py` | Picks params on TRAIN only, scores on unseen TEST. Anti-curve-fitting. |
| `data.py` | Synthetic OHLCV (Ornstein-Uhlenbeck) fixture + CSV loader. `kappa=0` → random walk (no edge); `kappa>0` → reverting (real edge). |
| `fetch_data.py` | Run LOCALLY to pull real SPY/QQQ via yfinance (sandbox has no internet). |
| `forecast_kronos.py` | Run LOCALLY (needs torch + HF download). Causal walk-forward Kronos forecaster → caches next-bar return to `<ticker>.kronos.csv`. `--mock` tests plumbing with no model. Frequency-agnostic (daily/intraday). |
| `run.py` | Entry point. Cost-regime table + walk-forward row. Auto-adds a `kronos` row + Kronos OOS walk-forward if a `.kronos.csv` sidecar exists. |
| `scan.py` | **Wide scan** (plan/11 §4). Thin wrapper: loops `walk_forward` over (ticker × strategy × grid) and ranks the OOS-net-of-costs results, scoring buy&hold + random through the SAME folds. If `realdata/spy.csv` exists it also judges every result **vs holding SPY over the same window** (the opportunity-cost bar). Verdict `EDGE?` requires beating **SPY + random** AND positive return AND the plan/14 I0.1 power check on the active return not FAIL AND **deflated Sharpe ≥0.95** (multiple-testing discount) — trades/fold stays a display column and a red-flag note only (I0.3, 2026-09-14: it no longer demotes a verdict on its own) — less-bad losers are `suspect`, not survivors, and each top name gets auto **red flags** explaining why. The printed "dead" bucket is split into `FAIL` (the power check rules out an edge worth trading) and `INCONCLUSIVE` (the test couldn't tell). ~40 ms/backtest. On the curated 30-name universe (slimmed 2026-07-06): **93 backtests → 0 EDGE?, 3 suspect, 90 FAIL/INCONCLUSIVE** (the honest base rate — 0 clean single-name edges; matches the earlier 0/309 on the ~100-name universe, archived in `realdata_archive_97/`). Also runs **live in the browser** via `/api/engine/scan` (Engine Room, 2026-07-06). `scan.py --log` records the meaningful rows (edges + gate-2 suspects) into `verdicts.jsonl` via `verdict_log.scan_row_to_record` (2026-07-11). |
| `fetch_universe.py` | Run LOCALLY (internet + yfinance). Batch-fetches a curated **liquid** universe of adjusted daily bars into `realdata/` (gitignored — vendor terms): SPY (benchmark) + a deliberately small, boring **30-stock core** across 6 sectors — no penny/pre-IPO/leveraged names (slimmed from ~97 on 2026-07-06, quality over quantity; Tenzing's call to ratify or widen). Then `scan.py`/`xsect.py` pick them all up. `python3 fetch_universe.py [EXTRA TICKERS…]`. Also exports `SECTORS` (ticker → sector), the shared grouping source of truth used by `engine_api.py`. |
| `xsect.py` | **Cross-sectional panel engine** (Thesis 001). Monthly 12-1 momentum rank across the stock universe (ETFs excluded), top-10 equal weight, net of costs on full turnover, `weights.shift(1)` no-lookahead. Canonical spec only (n_trials=1 — no grid). Judged vs **EW-universe** (the honest bar vs survivorship), random picks, and SPY, plus a per-year split, a **regime split, a monthly probabilistic Sharpe, and a sensitivity `sweep()`** (lookback × top-N neighbors — reported as robustness, never selection) — all now computed **vs EW-universe (active return)**, not vs zero (2026-09-14 gate fix; see `research/audits/2026-09-gates.md`). Run on two independent universes: ~90 names (2026-07-05) momentum **+972% vs +265% EW**; the slimmed 30-name core (2026-07-06) momentum **+309% vs +285% EW** — both beat SPY + random + EW on raw return, but the edge over EW-universe is **UNPROVEN**: active PSR 0.63 (not 1.00 — that number is P(Sharpe>0), which random top-10 also scores ~1.00 on), monthly active t=0.34 (need ~2+), 0/9 sweep neighbors significant (best t=1.18, not "9/9 then 7/9 beat EW"), 156% of the edge from one year (2024), t drops to −0.03 ex-NVDA. Pending Tenzing's sign-off either way. Also runs **live in the browser** via `/api/engine/momentum` (Engine Room, 2026-07-06). `xsect.py --log` records one Thesis-001 panel verdict (EW-universe as the honest bar, active PSR as the deflated-Sharpe field) into `verdicts.jsonl` (2026-07-11). |
| `export_track_record.py` | Run LOCALLY. Writes `webapp/lib/track_record.json` (wide-scan summary + Thesis 001 + verdict counts) from the same engines that produced the verdicts; committed so the deployed app shows real research without the backend. Rerun + commit whenever the record changes. |
| `api_server.py` | FastAPI wrapper around the harness. `/api/run` (single-ticker via `export_results.build`; each walk-forward entry now carries a `diagnostics` block — deflated Sharpe, per-year, regime split, red flags — that the webapp's panel ⑤ renders, 2026-07-11) + the **Engine Room** routes (2026-07-06): `/api/universe` (per-ticker data provenance), `/api/engine/scan` (live `scan.scan_universe`), `/api/engine/momentum` (live `xsect` pipeline), `/api/alpaca/status` (paper account, graceful when keys absent). Deps: `requirements-api.txt` (now includes `alpaca-py`). |
| `engine_api.py` | Engine Room plumbing (2026-07-06). `ensure_universe_data()` self-populates `data_cache/` on the deployed backend (realdata/ is gitignored): one **batched Alpaca** request first (keys present) → batched **yfinance fallback**, 30-min TTL cache, `?refresh=true` bypass, and a per-ticker provenance manifest (realdata / cache / alpaca / yfinance-fallback) so the data panel shows the actual vendor. Wraps `scan.py`/`xsect.py` **unmodified** into JSON-safe payloads; no new backtest math. Loads `.env` itself (stdlib) so local runs pick up the Alpaca keys. |
| `diagnostics.py` | **Robustness / multiple-testing filter** (plan/10 Part B). From the walk-forward output: **Deflated Sharpe** (Bailey–López de Prado — P(edge is real, not best-of-N luck); no scipy — normal CDF via `math.erf`, inverse via Acklam), per-year return+Sharpe (one-year-wonder), trades/fold, SPY-tagged regime split, and `red_flags()` → plain-English reasons a result may be fake. `python3 diagnostics.py` self-tests edge vs noise. |

## Run it
```bash
python3 run.py            # synthetic data, always works
python3 fetch_data.py SPY # locally only; writes spy.csv
python3 run.py spy.csv    # real data
python3 fetch_universe.py # locally only; fills realdata/ with the liquid universe
python3 scan.py           # rank the curated library across every realdata/*.csv (vs SPY)
python3 scan.py realdata/tqqq.csv f.csv   # scan a chosen subset

# Kronos (run LOCALLY, in a clone of github.com/shiyu-coder/Kronos or with it on PYTHONPATH):
python3 forecast_kronos.py realdata/tqqq.csv --mock          # plumbing test, no model
python3 forecast_kronos.py realdata/tqqq.csv --device cpu    # real zero-shot forecast
python3 run.py realdata/tqqq.csv                             # 'kronos' row appears automatically
```
Deps: pandas + numpy (yfinance only for `fetch_data.py`).

## Reading the output (don't get fooled)
- **FRICTIONLESS** = the lie. Raw signal only; ignore for decisions.
- **LIQUID ETF (3/1 bps)** = the truth for stocks. Not clearly positive here → dead.
- **CHEAP OPTION (300/50 bps)** = why naive options trading is ruin; active strategies → ~−100%.
- **OOS combined (walk-forward)** = the only number not lying. On the synthetic
  fixture it looks great *only because mean-reversion was baked in* (`kappa=0.04`).
  **Trust real-data OOS only.**

## Verified correct (2026-06-12)
Ran the harness and the core validation claims; all hold:
- Random walk (`kappa=0`) → mean-reversion loses **−51%** even frictionless → no hallucinated edge. ✅
- Edge present (`kappa=0.04`) → detected frictionless (+16.5%), eroded by costs (+6.3% ETF, −99.9% options). ✅
- No-lookahead is structural: `shift(1)` lives in the engine, not the strategies. ✅

## Key design invariants — preserve these when editing
1. **No lookahead stays in the engine.** Position at bar `t` is earned on bar `t+1`
   (`held = pos.shift(1)`). Never move this responsibility into a strategy.
2. **Costs are non-negotiable.** Every real verdict is net of `costs.py`. The
   FRICTIONLESS row exists only to expose the gap.
3. **Param selection respects the train/test boundary** in `walkforward.py`.
   Rolling windows are causal so positions can be precomputed on the full series,
   but *only prior data* may choose parameters.
4. **Metrics are slice-safe** (equity recomputed from `net`) — required for fold scoring.
5. New strategies are just a function `(prices, **kw) -> position Series in [-1,1]`.
   They must clear the same OOS-net-of-costs bar as everything else.

## Cost policy — free by default
Default to free tools, data, and infra (yfinance / Alpaca free daily bars / pandas / numpy /
Vercel free tier / Alpaca **paper**). A paid dependency (e.g. Alpaca's ~$99/mo live SIP feed,
managed DBs, paid APIs) is adopted **only** when it's ~20x more helpful than the free path
**and** Tenzing signs off first. Never assume a paid service; propose it and justify the 20x.
"Folds," "walk-forward," "diagnostics," etc. are compute on data we already have — they cost $0.

## Next steps (from README)
1. Real data: `fetch_data.py` for SPY/QQQ/IWM, then `run.py spy.csv`. Expect edge to
   mostly vanish after costs — that's the honest base rate.
2. **Kronos as a signal**: BUILT (zero-shot). `forecast_kronos.py` → `kronos_signal`.
   Run it locally on the six `realdata/` tickers and read the Kronos OOS walk-forward
   row. Only if zero-shot shows a non-trivial OOS-net-of-costs edge is finetuning
   (Qlib pipeline, multi-GPU) worth the cost. Expect it to mostly fail on daily bars —
   Kronos is strongest intraday, which `forecast_kronos.py` already supports via data swap.
3. Paper-trade survivors against real quotes (Robinhood MCP) for a week+ before real money.

## Honest expectation
Most likely real-data outcome: nothing beats buy-and-hold after costs. The win is the
machine and understanding *why*. Only risk the $23 if something genuinely survives
walk-forward on real data.

## Notes layer (Obsidian)
`Backtest.md`, `Costs.md`, `Run.md` are proper rendered notes (prose + code blocks +
wikilinks) covering 3 of the 8 sources. The `.py` files remain **canonical** — if you
change logic in a `.py`, update its note's code block to match. The notes also wikilink
to `[[Strategies]]`, `[[Metrics]]`, `[[Data]]`, `[[Walkforward]]`, which don't have notes
yet (they show as unresolved links — fine in Obsidian, and a marker for notes worth adding).

## Planning layer (living knowledge base) — start here for project direction
`PROJECT_PLAN.md` is the front door (Map of Content). The `.py` files are still canonical
for *engine logic*; the plan layer is canonical for *project direction, roles, and decisions*.
- `plan/` — 00-vision, 01-decision-log, 02-verdict-log, 03-roadmap, 04-glossary, 05-risk-register
- `roles/` — ROLE_Tenzing, standup-template (update routine), log-Tenzing (`roles/archive/` holds the
  retired role and log files)
- `research/` — _thesis-template.md + theses/
- `webapp/` — SPEC.md (prediction-vs-actual + pay-per-trade visualizer), options-modeling.md

Standing decisions live in `plan/01-decision-log.md` (e.g. options are PAPER-ONLY until a
strategy survives walk-forward OOS net of costs in the 300/50 bps regime; current focus is
the visualizer web app + a real Kronos run). **Maintenance rule:** when a work session
changes a decision/role/roadmap, update the relevant plan file the same session and keep
Claude's memory in sync.
