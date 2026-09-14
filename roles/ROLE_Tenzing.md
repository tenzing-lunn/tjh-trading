# Role — Tenzing (Engineering / The Machine)

See [[PROJECT_PLAN]] for the shared context. This is *your* lane only.

## Your one-line mission
Own the machine that decides what's real: the backtest harness, the data, the signals, and
the dashboard. If the code lies or peeks at the future, the whole project's
work is worthless — so your bar is correctness, not cleverness.

## What you own
- The whole `.py` pipeline (`costs.py`, `backtest.py`, `walkforward.py`, `strategies.py`,
  `data.py`, `forecast_kronos.py`, `run.py`).
- Data integrity (clean real data, no lookahead, no junk rows).
- Turning strategy theses into actual signal functions and running them.
- The deployed web app that makes results legible to non-coders.
- The engineering roadmap in [[plan/06-engineering-plan]].

## Deliverables (in order, no dates — just sequence)
See [[plan/06-engineering-plan]] for the full coding roadmap. The next 1-2 months optimize
for a deployed web app, not a perfect research platform.

1. **Clean the data.** Remove pre-IPO flat-padded rows from `realdata/nio.csv` and
   `realdata/sofi.csv`; remove or quarantine throwaway/mock Kronos outputs. Don't let dirty
   data produce fake edges.
2. **Export harness truth for the app.** Build a reproducible Python `results.json` export:
   prices, positions, trades, cost-regime metrics, OOS metrics, and data-quality warnings.
3. **Build and deploy the web app v1.** Read-only app: ticker picker, strategy picker, price
   chart, signal overlay, trade markers, net equity curve vs buy-and-hold, and verdict panel.
   This is the portfolio centerpiece and where your Vercel learning lands.
4. **Make the app interview-strong.** Add README/demo flow, architecture explanation,
   no-lookahead explanation, and public-safe sample results.
5. **Run Kronos for real.** Locally, not `--mock`, on all six tickers. Read the
   OOS-net-of-costs walk-forward row and write the result in the verdict log. This informs
   the research story but does not block app v1.
6. **Implement accepted strategy theses.** When a real thesis is written, turn it
   into `(prices, **kw) -> position Series in [-1,1]`, run it, and verdict-log it.
7. **Fill the missing Obsidian notes:** [[Strategies]], [[Metrics]], [[Data]],
   [[Walkforward]] (currently unresolved wikilinks). Keeps the `.py` ↔ notes in sync.

## How your work is graded (be harsh with yourself)
- **No-lookahead stays structural.** Position at bar `t` is earned on `t+1` (`pos.shift(1)`)
  and that logic lives in the *engine*, never in a strategy. If you ever move it, you've
  broken the one invariant that makes our results trustworthy.
- **Every verdict is net of `costs.py`.** Frictionless numbers are for diagnosis only.
- **A green result you can't explain is a bug, not a win.** Suspiciously good = look for a
  leak first.

## What you're here to learn (your CLAUDE.md goals, applied)
Git/GitHub collaboration, Supabase (RLS, edge functions, migrations) and Vercel via the
dashboard, MCP wiring (Robinhood data), and system design — keeping the harness modular as
strategies pile up.

## Your handoffs
- **To yourself, across roles:** a written thesis + sizing rules → turn it into a signal + run
  it; the real cost numbers per instrument → plug them into `costs.py`'s regimes so the
  verdict reflects reality, not a guess.
- **To everyone else:** the deployed app + verdict log, so non-coders can see what survived.

## The trap for you specifically
You can build anything, so you'll be tempted to add features (more signals, fancier model,
finetuning Kronos) before the simple question is answered. Don't. Finetuning Kronos
(Qlib, multi-GPU, real money) is only justified if zero-shot already shows an OOS edge.
Resist scope creep; ship the truth first.
