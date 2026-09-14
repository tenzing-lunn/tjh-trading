# Start Here

Welcome to the algo-trading club workspace. Tenzing is testing whether he can find a real
trading edge with his own $3–5k, running the project with Claude subagents, using an honest,
skeptical process instead of guessing. This page is the front door. If you only read one
page today, read this one.

## The mission, in one sentence
Find ONE signal that beats just holding the S&P 500 (SPY), *after real trading costs*,
on data it has never seen before — and prove it honestly before we trust it with money.

## The one rule (read this every time)
**A strategy is only "real" if it beats buy-and-hold AND a random strategy, on data it
wasn't tested on, after costs.** Almost nothing survives this. That's the point — the
whole system exists to stop us from fooling ourselves, not to flatter our ideas.

## Where we are right now (short version)
- The backtesting engine (the code) works and is honest: no cheating, no seeing the future.
- We've tested it on real stock data. So far: **zero single-stock timing strategies survive.**
  That's expected and it's the system working correctly.
- One idea — "buy the stocks that have been winning" (momentum) — looks promising across a
  30-stock test group, but it's **not yet approved.** It needs Tenzing's sign-off
  before it'd ever be paper-traded, let alone use real money.
- **Nothing is happening with real money right now, and nothing will until this process says so.**

See the **What To Do Right Now** page for exactly what's owed to the process.

## How this workspace is organized
- **What To Do Right Now** — the only page you need to check every week. Open items live here.
- **Roles** — what Tenzing owns, and why the judgment calls can't just be done by AI.
- **Strategy Ideas (Theses)** — every trading idea we've tested, written as a falsifiable claim.
- **Results So Far** — the track record. Most rows say "no edge" — that's a feature, not a failure.
- **Roadmap** — what's done, what's next, what's later.
- **Glossary** — plain-English definitions for every term you'll see (Sharpe ratio, OOS, etc.).
- **Decisions We've Made** — the short list of standing rules we've agreed on and why.

## The non-negotiables (these override enthusiasm)
1. A strategy only counts if it beats buy-and-hold *and* random, out-of-sample, after costs.
2. Money stays in index funds / paper trading until a strategy clears rule #1. We build first, fund never on hope.
3. Options are paper-only until a strategy survives the (expensive) options cost regime. Our own testing shows naive options trading loses ~100%.
4. No outside money, ever. This is the three of us and our own money, not a fund.
5. Honesty is the asset. "We tested 10 ideas and 9 failed" is a *better* result than one fake winner, because it's true.

## Technical home (for the curious)
All of the actual code and detailed research notes live in the GitHub repo, not in Notion.
Notion is the front door for decisions and to-dos; the repo is the source of truth for how
the engine works. Ask Tenzing if you ever want a walkthrough of the code — you don't need to
read it to do your job here.
