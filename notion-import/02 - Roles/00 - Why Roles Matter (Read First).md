# Why Roles Matter (Read First)

One person, several jobs, one machine. The engine (built with Claude subagents) can run any
test instantly and for free — compute is not the bottleneck. **Judgment is.** This page
explains why the strategy-judgment and cost/universe-judgment jobs specifically cannot be
handed off to an AI on its own, even though AI wrote most of this workspace.

## The short version
An AI (or any backtest) can tell you a number. It cannot tell you whether to *believe* the
number. That belief requires:
1. **A real-world reason** the pattern should exist, and
2. **Honest skepticism about whether the test itself is trustworthy.**

Both of these require judgment calls that have no single correct formula — if they did, we'd
just code the formula and skip the human. They exist precisely *because* they're not
mechanical. Claude's Fable model runs an independent audit of the reasoning and the numbers,
but the final call stays Tenzing's.

## Why the strategy-judgment job can't be automated
An AI can find patterns in historical data all day — that's the easy part, and it's also the
trap. Any large enough dataset has *some* pattern that looks good by pure chance (this is
called overfitting / data mining). The only defense is asking, before you trust a pattern:
**"why would this keep working, and who is losing money to make that happen?"**

That question requires understanding *human behavior* — why investors underreact to good
news, why they panic-sell, why institutions are slow to react — and then making a *judgment
call* about whether that behavior is still true today and will stay true. An AI can describe
the theory (it did, in the momentum thesis), but it cannot tell you whether *you* find it
convincing enough to risk money on, because that's not a factual question — it's a risk
decision that a human has to own. If a strategy blows up, "the AI told me it would work" is
not an acceptable answer. "I reviewed the reasoning and signed off" is what a real research
process requires — and that ownership is the whole point of this role.

## Why the cost/reality-check job can't be automated
The backtest engine can compute a return, a Sharpe ratio, a drawdown. What it cannot do is
decide, on its own, **how pessimistic to be about costs, or how much to trust a result that
only "worked" because we only tested stocks that happened to survive and do well** (this is
called survivorship bias — see the Glossary).

Those are calibration judgments, not calculations:
- Real trading costs (spread, slippage, fees) vary by broker, order size, and market
  conditions. Someone has to decide what's realistic *for us specifically*, and err on the
  side of pessimism — an AI defaults to whatever number it's given, it doesn't independently
  distrust its own inputs.
- Deciding "is this result real or lucky" is a judgment call informed by market experience
  and healthy paranoia, not a single statistic. The tools flag red flags automatically, but
  *acting* on them — killing a strategy that looks exciting — is a human choice that requires
  someone willing to say "no" to a good-looking number.

## The pattern
Notice both jobs are fundamentally about **being the person willing to say "I don't believe
this" to a number that looks good.** That's uncomfortable, it's not a task you can specify
precisely enough to code, and it's also exactly the skill that makes someone a good analyst,
researcher, or portfolio manager — which is why this is genuinely useful experience, not
busywork.

## What the engineering role is, for contrast
Engineering is more automatable in principle — "build a correct, honest backtest" is a
well-specified engineering problem, which is exactly why AI assistance has sped it up a lot.
Strategy judgment and cost/universe judgment are not.
