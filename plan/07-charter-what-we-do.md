# 07 — Charter: What We're Doing / What We're Not Doing

Home: [[PROJECT_PLAN]] · Roles: [[roles/ROLE_Tenzing]]

*The one-page answer to "what is this project actually trying to do." If you read nothing
else, read this. Last set: 2026-06-30.*

---

## The goal (in one sentence)
**Find ONE trading signal that beats buy-and-hold out-of-sample, net of realistic costs, on
real equity data — and prove it honestly.** We have zero so far. That's normal. The deliverable
right now is the *machine and the skill*, not profit.

## What "done" looks like for phase 1
A single strategy that, on real daily data it has never seen, beats just holding SPY over the
same window *after* costs, in our walk-forward test. Until that exists, nothing else matters.

## What we ARE doing
- **Trading liquid US equities & ETFs first.** SPY/QQQ/IWM + a few liquid large caps. Free,
  clean data; small spreads; survivable costs.
- **Swing-style holding, not day trading.** Daily bars → decide a position once per day, hold
  overnight to days/weeks until the signal flips. (Intraday is a *later* option; Kronos is
  stronger intraday, but we walk before we run.)
- **Paper trading on Alpaca.** Free paper account, real API, built for automation. Survivors
  get paper-traded against live quotes for weeks before anyone discusses real money.
- **Keeping the $3–5k parked in an index fund** earning the market return until a strategy
  clears the bar. Money is separate from software (see [[plan/01-decision-log]]).
- **One signal at a time, with an economic reason.** Tenzing writes a thesis (*why* an edge
  exists), builds + runs it, checks it after real costs and logs the verdict.

## What we are NOT doing (and why)
- **NOT day-trading small caps.** Hardest, most-competitive, worst-data, highest-cost game in
  the market. The PDT legal barrier is gone (see below) but the *edge* problem is untouched.
  This is where beginners donate money.
- **NOT trading options with real money** — paper-only until a strategy survives the 300/50 bps
  "cheap option" cost regime. Naive options → ~−100% in our own harness. (Standing decision.)
- **NOT chasing strategy quantity.** Running thousands of strategies to find "winners" is the
  multiple-testing trap: some look brilliant by pure luck. We test few, well-reasoned ideas
  and demand each survive out-of-sample net of costs.
- **NOT pooling outside money / managing strangers' money.** Securities-law exposure. This is
  Tenzing's own money; long-term ambition is a Fordham *research/education* club. (Standing decision.)

## Reference facts (verified 2026-06-30)
- **PDT rule changed.** As of 2026-06-04 (FINRA), the $25k pattern-day-trader minimum is
  eliminated and replaced by intraday margin standards; margin accounts need only $2k minimum
  equity. *This removes a legal constraint, not the reason day trading is hard.*
- **Alpaca real costs:** $0 commission on US stocks/ETFs; options ~$0.65/contract each way;
  margin interest ~6.5% (don't borrow); wire withdrawals $25/$50 (ACH free); tiny regulatory
  pass-through on sells. **Hidden one:** free market data = IEX feed only (~2–3% of volume);
  full real-time SIP data is a paid sub (~$99/mo). Daily-bar backtest + paper = free is fine.
- **Never generate price data with an LLM** (DeepSeek/Claude/etc.) — it hallucinates fake
  prices. Use real sources (yfinance, Alpaca data API, Stooq) and let the LLM write the
  fetch *script*, not the numbers.

## Who does what next
**Tenzing (Strategy & Risk, with Claude subagents):** write the *first real strategy thesis* in
`/research/` using the template in [[research/_thesis-template]] — the claim, *why the edge
exists and who's on the other side*, why it persists, how to test it, what would kill it, and
a pre-registered prediction. One good thesis unblocks the whole pipeline. Also draft basic
sizing rules (max % of pool per position, when to cut a loser).

**Tenzing (Costs & Reality):** build the **real cost table** — realistic spread + slippage + fee
in bps for (a) liquid ETF, (b) single liquid stock — from actual Alpaca/market numbers, erring
pessimistic. Define the **tradable universe** (which liquid tickers, what to exclude). These
feed `costs.py` and decide whether any verdict is real. Own the **verdict log** with the
"vs SPY over the same window" benchmark on every result.

**Tenzing (Engineering):** load a clean liquid-equity universe (SPY/QQQ/IWM + large caps) via
`fetch_data.py`; encode the cost table into `costs.py`; implement the first thesis as
a signal and run the walk-forward; set up the shared Alpaca paper account + API keys. Keep
shipping the visualizer per [[plan/06-engineering-plan]].

## The bar every idea must clear (tape this to the wall)
> Beats buy-and-hold, out-of-sample, net of `costs.py`, on real data it has never seen.
> If you can't explain *why* it works, assume it's a bug or luck — not a win.
