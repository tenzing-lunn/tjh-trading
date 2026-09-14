# Role — Henry (Costs, Execution & Measurement / The Reality Check)

See [[PROJECT_PLAN]] for shared context. This is *your* lane only. You do **not** need to
code. You are the one who makes sure our results reflect the *real* market, not a clean
fantasy — and the one who honestly tracks whether we're actually beating the benchmark.

## Your one-line mission
Own the brutal realities that kill most strategies: transaction costs, what's actually
tradable, and honest measurement against buy-and-hold. If Jonathan is the offense, you're
the accountant who proves whether the offense actually scored *after the bills are paid.*

## What you own
- **Cost assumptions.** Real spreads, slippage, and fees per instrument we trade.
- **The instrument universe.** What we're allowed to trade and why.
- **The verdict log + benchmark tracking.** Honest record of what we tested and whether it
  beat SPY.

## Deliverables (sequence, no dates)
1. **Build the real cost table.** For each instrument type we'd trade (liquid ETF, single
   stock, option), find realistic spread + slippage + fee numbers in basis points. These
   feed `costs.py`'s regimes. Use real Robinhood/market data, not guesses. *This is the
   single most important input to whether a strategy is "real."*
2. **Define the tradable universe.** Which tickers, why, and what to exclude (e.g., the
   pre-IPO junk in nio/sofi, illiquid names with huge spreads). Liquidity is a feature.
3. **Own the verdict log — the JUDGMENT, not the typing.** The harness will *auto-append* the
   mechanical row (what was tested, OOS-net-of-costs number, vs-SPY benchmark) — that's a
   `run.py` job, not a human one (see [[plan/01-decision-log]] 2026-06-30). **Your** column is
   the part a machine can't write: *is this real or luck?* Flag regime dependence, suspicious
   trade counts, selection bias, and whether the result actually justifies advancing. A number
   with no skeptical interpretation is just data; you turn it into a verdict.
4. **Trade journal (once anything is paper-traded).** Every paper trade: thesis, entry,
   exit, expected vs actual cost, what we learned. Reality vs backtest is where the lessons live.

## How your work is graded
- **Costs are non-negotiable.** If your numbers are too optimistic, every verdict is a lie.
  Err toward *pessimistic* costs — survive the worst case.
- **Every result is compared to the benchmark.** "Strategy made +4%" is meaningless alone.
  "+4% vs SPY's +9% over the same window, after costs" is the truth. Always include the
  benchmark.
- **No edits to the log to make us look good.** The honest record is the asset. A clean
  story of "we tested 10 things, 9 had no edge" is more credible than a fake winner.

## What you're here to learn
Market microstructure (why costs are what they are), benchmarking and performance
attribution, and the discipline of honest measurement. In a finance interview, "I built the
cost model and proved most of our strategies didn't beat the index net of costs" is a
*stronger* signal than claiming you found a money printer.

## Your handoffs
- **To Tenzing:** the cost table → he encodes it in `costs.py`; the universe → he runs the
  harness on it.
- **To Jonathan:** the real costs → he checks his sizing/edge survives them.
- **To everyone:** the verdict log + benchmark comparison, every cycle.

## The trap for you specifically
Being too generous with cost assumptions because pessimistic costs "kill" exciting
strategies. That's backwards — costs that are too low are how retail traders convince
themselves they have an edge and then lose money live. Your pessimism is the club's
protection. Be the one who says "after real costs, this is dead."
