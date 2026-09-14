# Web App — Options Modeling (and what we're missing)

Home: [[PROJECT_PLAN]] · See also [[webapp/SPEC]], [[plan/04-glossary]]

*This file answers your exact question: "what are we actually building, and what are we
missing?" for the options part. Read this before writing a line of options code.*

## The honest hard truth up front
**An option's value is NOT just stock direction.** It depends on strike, time to expiry,
**implied volatility**, and the **Greeks** (delta/theta/gamma/vega). The killer is **theta
decay**: every day, an option you hold loses value, all else equal. So you can predict
direction *correctly* and still lose money. Any options simulator that ignores this is a toy
that will make us feel smarter than we are. We label honestly or we don't build it.

## What we want the app to do
"If our model said BUY on date X, and we'd bought a specific call (strike/expiry), what would
that option have been worth as the trade played out — net of the (large) cost of trading it?"

To answer that faithfully you need, for each day of the trade:
1. The **actual market price of that specific option** (a specific strike + expiry), with its
   bid/ask, OR
2. A **pricing model** (Black–Scholes) fed a realistic **implied volatility** for that
   contract.

## What we're missing (the real bottlenecks — name them so we don't pretend)
1. **Historical options data is the wall.** Free, deep historical options quotes basically
   don't exist. The Robinhood MCP gives **current** option chains/quotes, not years of
   history. So a faithful "what would this option trade have done in 2022" backtest is
   **data-blocked** today.
2. **Two honest ways around it:**
   - **(a) Record forward.** Use Supabase + a daily job to **save live option chains from
     now on**. In a few months we have our own real dataset. Slow but truthful. *This is the
     recommended path and the real reason to build the Supabase layer.*
   - **(b) Approximate with Black–Scholes.** Price options from the stock's history + an IV
     assumption. Fast, but **label every such result "APPROXIMATE — modeled, not market."**
     Good for teaching the Greeks; not good enough to risk money on.
3. **Fills/liquidity lie.** Options bid/ask spreads are wide. Assuming you buy/sell at
   mid-price is the classic self-deception. The pessimistic cost model matters *more*
   here — we assume we cross the spread, not split it.
4. **Corporate actions, dividends, early assignment, after-hours** — secondary, but real;
   note them, don't drown in them yet.

## Recommended build order for options
1. **Don't start with options.** Start with equities ([[webapp/SPEC]] Phase A) where data is
   clean and the harness already works.
2. Add a **Black–Scholes "approximate" overlay** to teach theta/IV visually — clearly
   watermarked APPROXIMATE.
3. Start **recording live chains daily** (Supabase) so that *future* options backtests can be
   real.
4. Only after we have real recorded data + a strategy that survives the 300/50 cost regime
   OOS do we even discuss real options money. (Decision: [[plan/01-decision-log]].)

## The one-line takeaway
We're building an options *visualizer/teacher*, not an options *backtester* — yet — because
we don't have the historical data to backtest honestly. The app's first job is to make the
cost-and-theta reality undeniable, not to find a winning options trade.
