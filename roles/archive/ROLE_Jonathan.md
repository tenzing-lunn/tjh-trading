# Role — Jonathan (Strategy & Risk / The Offense)

See [[PROJECT_PLAN]] for shared context. This is *your* lane only. You do **not** need to
code. You need to think clearly about *why an edge would exist* and *how much to bet*.

## Your one-line mission
Supply testable strategy ideas with a real economic reason behind them, and the risk rules
that keep one bad trade from blowing up the pool. Tenzing can build any idea — your job is
to make sure the idea isn't just noise dressed up as a signal.

## What you own
- **Strategy theses.** The hypotheses we test.
- **Position sizing & risk rules.** How much we put on a given trade, and the limits.

## Deliverables (sequence, no dates)
1. **Write strategy theses** — one short doc each in `/research/`. A thesis is NOT "RSI
   below 30 means buy." It's: *what real-world behavior creates this edge, who is on the
   other side of the trade, and why does it persist?* Template below. Start with one, then
   keep them coming.
2. **Define sizing rules.** For any strategy we'd actually fund: max % of the pool per
   position, max total exposure at once ("portfolio heat"), and when we cut a loser. Write
   it as plain rules Tenzing can encode.
3. **Pre-register predictions.** Before Tenzing runs a thesis, write down what you *expect*
   the result to be. Being wrong on the record is how you learn what actually drives returns.
4. **Review results with skepticism.** When something looks like it works, your job is to
   argue *why it might be fake* (data mining, regime luck, survivorship) before we believe it.

### Strategy thesis template (copy this per idea)
```
Strategy: <name>
The claim: <one sentence — what edge are we capturing>
Why it exists: <the economic/behavioral reason. Who's on the other side, and why
               are they willing to lose to us?>
Why it should persist: <why hasn't it been arbitraged away?>
How to test it: <what signal, on what instruments, over what period>
What would kill it: <what result would make us abandon it>
My prediction: <does it beat buy-and-hold OOS net of costs? yes/no/unsure + why>
```

## How your work is graded
- **A thesis with no "why it exists" is rejected.** If the only reason is "it backtested
  well," that's the curve-fitting trap and Tenzing should bounce it back to you.
- **Quality of reasoning beats win rate.** A well-argued thesis that fails the harness is a
  *success* — you learned a true thing. A vague idea that happened to pass is worthless.

## What you're here to learn
How to translate market intuition into a *falsifiable* hypothesis, position sizing and
risk-of-ruin math, and reading a walk-forward result without fooling yourself. This is the
core skill of a quant researcher — and it's exactly what you can defend in a finance interview.

## Your handoffs
- **To Tenzing:** thesis doc + sizing rules → he implements and runs them.
- **From Tenzing:** the OOS-net-of-costs result → you interpret it and decide: iterate, kill,
  or (rarely) advance toward paper trading.
- **With Henry:** he supplies the real cost assumptions; you make sure your sizing rules
  survive *after* those costs, not before.

## The trap for you specifically
Falling in love with an idea because it's elegant or because it backtested well once. The
market doesn't pay for elegance. Assume every edge is fake until it survives out-of-sample,
net of costs, on data it's never seen — and even then, stay suspicious.
