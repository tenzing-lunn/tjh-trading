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
| `scan.py` / `xsect.py` | Wide scan (ticker × strategy × grid, walk-forward OOS vs SPY/random/B&H with deflated-Sharpe + red flags) and the Thesis 001 cross-sectional momentum panel engine. Both also run **live in the browser** via the Engine Room (`/engine`, 2026-07-06). |
| `api_server.py` / `engine_api.py` | FastAPI service: `/api/run` plus the Engine Room routes — `/api/universe` (per-ticker data provenance: Alpaca first, yfinance fallback, TTL-cached), `/api/engine/scan`, `/api/engine/momentum`, `/api/alpaca/status` (paper account, graceful when keys absent). `engine_api.py` calls the engines unmodified — no new backtest math, no math in JS. |

## Run it
```bash
python3 run.py            # synthetic data, always works
python3 fetch_data.py SPY # locally only; writes spy.csv
python3 run.py spy.csv    # real data

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
Codex's memory in sync.

## Imported Claude Cowork project instructions

I'm Tenzing, trying to turn my invested 3-5k. Maximizing profit, minimizing risk. I'm introductory to trading, a CS/Math major, running this project with Claude subagents. Be my mentor, teacher, advisor, and guide - be supportive but harsh when making bad decisions (always grill me about decisions to make sure all options are viewed.)
