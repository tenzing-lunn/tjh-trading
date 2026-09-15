# The Skeptic's Machine — an honest backtesting lab

**Live app:** https://webapp-zeta-liart.vercel.app (the backend runs on a free server, so the
first load can take ~30s to wake up)

## What this is, in one paragraph
Tenzing wanted to trade a few thousand dollars of his own money *without fooling himself*. So
instead of guessing at trades, this project built a machine that tests trading ideas against
about 8 years of real stock prices, run with Claude subagents doing the engineering, research,
and auditing. It charges realistic trading costs and only grades an idea on data it has never
seen. The machine's job is to **kill bad ideas**. Most ideas die, and that's the point: it
means the machine isn't flattering us.

## The one rule
> An idea is only "real" if it beats the dumb options (just buy the stock and hold it, or
> trade at random) **on data it wasn't tuned on, after paying costs.**

## Current work: intraday data foundation

The active plan is [plan/14-intraday-plan.md](plan/14-intraday-plan.md). The minute
cache covers 32 symbols from 2016; calendar checks exclude 98 bad symbol-days.
Measured quote spreads are in [Costs.md](Costs.md). Session-aware execution,
feed-delay enforcement, and the signed intraday cost regime are still required.

Use the project's virtual environment for data work:

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python audit_intraday.py  # local cache inventory
.venv/bin/python dq.py             # certify minute files; check daily CSVs
.venv/bin/python spreads.py        # summarize an existing completed quote cache
```

On a fresh cache, `spreads.py --fetch` freezes and fetches the quote sample plan;
`spreads.py --backfill` resolves missing snapshots at unchanged timestamps.
Run one Alpaca collector at a time. Daily CSV admission now rejects malformed
files; `data.load_intraday` returns separate, certified sessions. See the
[data audit](research/audits/intraday-data.md) for reproduction and limitations.

## What we found so far (the short version)
| What we tested | Result |
|---|---|
| 3 classic single-stock strategies (below), tried on 31 stocks = 93 tests | **0 edges, 3 suspects, 76 FAIL, 14 INCONCLUSIVE** (2026-09-14 rerun). |
| The same thing earlier on ~100 stocks = 309 tests | **0 passed.** So the "nothing works" result wasn't about which stocks we picked. |
| **Thesis 001: momentum.** Every month, buy the 10 stocks that rose the most over the past year | **Looked like it passed, but a closer check (Sept 2026) says unproven.** **+309%** vs +285% for owning all 30 equally and +180% for holding SPY (2019–2026, after costs). But its lead over "own all 30" is too small to tell apart from luck. The t-stat is 0.34, where ~2 is needed, and it won only 48% of months. Remove NVDA and the lead disappears. It also loses money in sideways, choppy markets. Not traded with real money. |

**Takeaway:** simple chart-pattern tricks on one stock at a time don't beat the market once you
pay costs. A well-known, research-backed idea (momentum across many stocks) is our best
candidate, but 7 years of data can't prove it yet. We haven't risked a dollar. See
*The plan from here*.

---

## What data we use
- **What it is:** a daily price summary for each stock. Every trading day has one row: open,
  high, low, close, and volume (how many shares traded).
  Prices are *adjusted*, meaning splits and dividends don't create fake jumps.
- **Where it comes from:** Yahoo Finance, free, via the `yfinance` Python library. The live
  app tries Alpaca first (a broker with a free data feed) and falls back to Yahoo.
- **Time span:** July 2018 → July 2026. That's ~8 years, or ~2,010 trading days per stock.
- **Which stocks (30 + SPY):** large, heavily traded US companies across 6 sectors. There are
  no penny stocks and no leveraged products.
  - Tech: AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, ADBE, CRM, ORCL
  - Financials: JPM, BAC, GS, MA, V
  - Healthcare: UNH, JNJ, LLY, ABBV, MRK
  - Consumer: WMT, COST, HD, PG, KO, MCD, NKE
  - Energy/Industrial: XOM, CVX, CAT
  - **SPY** (an S&P 500 index fund) is the benchmark: "what if you just bought the market?"
- **It's not in this repo.** Yahoo's terms don't allow redistributing their data, so the
  price files are gitignored. You download your own copy with one command (see *Run it*).

## How the machine works (plain English)
1. **Load prices** for a stock.
2. **A strategy decides each day:** own it (+1), stay out (0), or bet against it (−1).
   Strategies we've tried:
   - **SMA crossover.** Buy when the short-term average price rises above the long-term
     average. The classic "trend" signal.
   - **Mean reversion.** If the price is unusually far below its recent average, bet it snaps
     back.
   - **Time-series momentum.** Own a stock if it went up over the past 6–12 months.
   - **Cross-sectional momentum (Thesis 001).** Rank all 30 stocks by their past-year gain and
     hold the top 10, rebalancing monthly.
3. **No peeking at the future.** A decision made on day *t* only earns day *t+1*'s return.
   This rule lives in the engine itself, so no strategy can accidentally cheat.
4. **Charge costs on every trade.** For big liquid stocks we charge 3 basis points (0.03%)
   of spread and 1 bp of slippage. Slippage means getting a slightly worse price than you
   expected. We also show a "frictionless" (no-cost) version, only to expose how much costs
   eat. And an "options-like" version (300/50 bps) shows why frequent options trading goes
   to ~−100%.
5. **Walk-forward testing: the anti-cheating step.** Every strategy has settings, like
   "which averages to compare." If you pick the settings that looked best over all 8 years,
   you're grading yourself on the answer key. Instead we cut the history into 6 chunks. We
   pick settings using only the past, test them on the next chunk, and repeat 5 times. Only
   those unseen test chunks count. That is the **out-of-sample (OOS)** result.
6. **Compare against the dumb options:** buy-and-hold, random trading, and holding SPY over
   the same dates.
7. **Honesty checks** (`diagnostics.py`) flag results that are probably luck:
   - **Too few trades.** 5 trades can't prove anything.
   - **A one-year wonder.** Most of the gain came from one lucky year, like 2020.
   - **Only works in one kind of market.** We split days into up, down, and sideways
     ("chop") markets and check each.
   - **The deflated Sharpe ratio.** The Sharpe ratio measures return per unit of risk. If
     you try 12 settings, one will look good by chance, and the deflated version discounts for
     that. It works out the probability the result is real and not luck. We require ≥ 0.95.

An idea gets the label `EDGE?` only if it clears **all** of these. Almost nothing does.

## Run it yourself
Needs Python 3.10+.
```bash
pip install -r requirements.txt   # just pandas + numpy
python3 run.py                    # works instantly on FAKE data (no internet needed)
```
The fake-data run is a self-test. The fake prices have a pattern deliberately built in, and
the machine should find it. On pure random prices it should find nothing, and it doesn't.

With real data:
```bash
pip install yfinance
python3 fetch_universe.py         # downloads the 30 stocks + SPY into realdata/
python3 scan.py                   # tests every strategy on every stock, ranks them
python3 xsect.py                  # runs Thesis 001 (momentum across the 30 stocks)
python3 run.py realdata/spy.csv   # detailed report for one stock
```

**How to read the output:**
- **FRICTIONLESS** is the fantasy version with no costs. Ignore it for decisions.
- **LIQUID ETF** is the realistic version for stocks.
- **OOS / walk-forward** is the only number that isn't lying to you.

## What's in the repo
| File | What it does |
|---|---|
| `costs.py` | Trading-cost model. The most important file. |
| `backtest.py` | Day-by-day simulator; enforces the no-peeking rule. |
| `strategies.py` | The trading ideas (each is just a function: prices in → daily positions out). |
| `walkforward.py` | The anti-cheating train/test loop. |
| `metrics.py` | Return, Sharpe, max drawdown (worst peak-to-bottom drop), win rate, trade count. |
| `diagnostics.py` | The "is this just luck?" checks and red flags. |
| `scan.py` | Runs every strategy on every stock and ranks the results. |
| `xsect.py` | The multi-stock engine for Thesis 001 (momentum). |
| `data.py`, `fetch_universe.py`, `fetch_data.py` | Fake-data generator, and downloaders for real data. |
| `verdict_log.py` → `verdicts.jsonl` | Automatically records every real result so nobody can quietly edit the track record. |
| `api_server.py`, `engine_api.py` | Wraps the engine as a web API for the app. |
| `webapp/` | The Next.js website (charts, cost sliders, the "Engine Room" that runs the scan live). |
| `alpaca_paper.py` | Hooks into an Alpaca **paper** (fake-money) account. Not trading yet. |
| `forecast_kronos.py` | Optional: plugs in Kronos, an AI price-forecasting model. Parked for now, because it's built for minute-by-minute data and we use daily. |
| `PROJECT_PLAN.md`, `plan/`, `research/` | The team's decisions, results log (`plan/02-verdict-log.md`), and the Thesis 001 writeup. |

## Where it stands
1. ✅ Engine built, tested on real data, and deployed as a website.
2. ✅ First research-backed strategy (momentum) run.
3. ⚠️ A closer check (Sept 2026) found momentum's edge over "own all 30" is not yet
   distinguishable from luck. **So the next job is proof, not trading.**

## The plan from here
The full plan, with every task and who builds it, is in
[`plan/12-real-markets-plan.md`](plan/12-real-markets-plan.md). The short version: each step
must pass before the next one starts, and **people, not code, decide** at each gate.

| Phase | What happens | Gate to move on |
|---|---|---|
| **0. Fix the machine** | Add the check that caught this: does a strategy beat "own everything equally" by more than luck? Audit the other checks for the same blind spot. | The machine's verdict matches the finding above |
| **1. Prove it** | Test momentum over ~100 years of free academic data (Ken French's library). Retest on a stock list with no hindsight (stocks that were in the S&P 500 *at the time*, including ones that later failed). Compare against MTUM, an existing momentum ETF. Find the trading cost at which the edge disappears. An independent audit follows. | **G1 (team):** it beats the alternatives by more than luck in all of these, or we drop it and move to the next idea |
| **2. Make it runnable (fake money only)** | Daily data refresh, a "what to hold this month" report, a script that turns that into Alpaca **paper** orders (dry run by default, and it refuses anything but the paper account), a trade journal, tests, and a safety audit. | Audit passes |
| **3. Risk rules** | Written limits: max loss before stopping, max per stock and per sector, what "broken" means. Plus a kill switch in code that refuses to trade past those limits. | Tenzing signs the policy |
| **4. Real-world costs** | Model taxes (monthly trading creates short-term gains) and measure real trading costs from paper fills. | Tenzing signs the real cost numbers |
| **5. Paper trade** | At least 3 monthly rebalances with fake money, comparing results with what the backtest predicted. | **G2 (team):** results in the expected range. Real money is a separate, later decision |

**Who builds it:** the work is split across Claude models by difficulty. **Fable 5.1**
(the most capable) designs the tricky tests and audits results for mistakes. **Opus 5** builds
the core engine changes and anything that touches orders. **Sonnet 5** handles routine
features, tests and the website. **Haiku 4.5** does simple jobs like data downloads. No AI agent ever
places a trade or makes a go/no-go call.

## Caveats (read before getting excited)
- **Survivorship bias.** Our 30 stocks are companies that are big and successful *today*.
  Anything picked that way looks great in hindsight. That's why momentum's real test is
  beating "own all 30 equally," not beating SPY. On that test, the lead (+309% vs +285%) is
  small enough to be luck.
- **One history.** 2019–2026 was mostly a bull market. The two stock lists are different, but
  both runs cover the same years.
- **Costs are estimates.** The 3/1 bps numbers are reasonable for big stocks but haven't been
  checked against real fills yet.
- **This is a student research project, not financial advice.**
