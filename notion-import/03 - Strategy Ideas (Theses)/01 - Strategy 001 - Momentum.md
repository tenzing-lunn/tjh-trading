# Strategy 001 — "Buy the Winners" (Cross-Sectional Momentum)

**Status: UNPROVEN (updated 2026-09-14). A deeper statistical check found the edge over
"just own the whole test group" is not distinguishable from luck — see the correction note
near the bottom. Nothing has been paper-traded or funded yet.**

## The claim
Stocks that have outperformed over the trailing 12 months (excluding the most recent month)
tend to keep outperforming over the next month. Every month, rank a group of large, liquid
stocks by their trailing return; buy the top 10, equal amounts of each; hold one month; repeat.

## Why it exists
Investors are slow to fully react to good news — analysts revise their estimates gradually,
big institutions build positions over weeks not seconds, and everyday investors are slow to
notice a trend. The people on the other side of this trade are investors who sell winners too
early (a well-documented bias) and people who don't care about this pattern at all (index
funds, value investors who intentionally avoid recent winners).

## Why it should persist
Momentum is one of the most heavily studied patterns in finance and hasn't been fully traded
away, likely because: (a) it doesn't work at massive scale without real risk (large funds got
badly burned by a "momentum crash" in 2009 and are cautious), (b) it requires real trading and
real costs that eat into it for anyone careless about execution, and (c) the psychology
behind it doesn't go away just because people know about it. That said — "it's a famous
pattern" is not proof it works *for us*, which is why it still had to pass the same bar as
every other idea.

## How it was tested
A dedicated testing tool that ranks a whole basket of stocks at once (the normal one-stock-
at-a-time tester can't do this). No peeking at future prices; realistic trading costs baked
in; and it's judged against not just "buy and hold SPY" but also "just own the whole test
basket, unpicked" — which is the harder, more honest bar (see Results So Far for why).

## What would kill it
Failing to beat *just owning the whole test group without picking winners*. If picking the
top 10 doesn't beat owning all 30, then "picking winners" isn't actually doing anything —
the good result would just be from being in stocks that happened to do well. Also: failing to
beat random picks, or the good years being carried by one lucky year.

## Result — run #1 (larger group, 2026-07-03)
Tested on ~90 well-known US stocks, 2019–2026. The momentum picks made **+972%** total,
vs. **+265%** for just owning the whole group, vs. **+180%** for holding SPY. It won 5 of the
last 8 years, including holding up much better in the bad year (2022): −2% vs −13% for the group.

## Result — run #2, a robustness check (smaller group, 2026-07-06)
Tenzing cut the test group down to a cleaner, smaller list of 30 well-known stocks (see
Results So Far for the list) and re-ran the *exact same* idea, unchanged. Momentum picks made
**+309%**, vs. **+285%** for owning the whole smaller group, vs. **+180%** for SPY — still
wins, just by a smaller margin on this different group of stocks. That the idea works again
on a different set of stocks is a good sign it's not a fluke tied to one specific list.

## 🚩 The honest catches (read before believing any of the above)
- **Every stock in our test group "survived" to today by definition** — we didn't include
  companies that went bankrupt or got delisted along the way. This makes every number above
  look better than real life, including the "just own everything" comparison — which is
  exactly why beating that comparison (not just beating SPY) is the real bar.
- **It loses money in choppy, sideways markets** — up to −22% to −39% depending on which test
  group. This is a strategy that does well when the market is trending, not in all conditions.
  Anyone approving this should expect real pain in a choppy year, not assume it always wins.
- **This is one 7-year stretch of history**, not several independent tests. A round of actual
  fake-money (paper) trading going forward is the real test of "does this keep working."
- **No short-selling tested** — the "textbook" version of this strategy also bets against the
  worst-performing stocks, which we're not doing (too risky/impractical at our account size).

## 🚩 Correction (2026-09-14): the numbers above weren't measuring the right thing
Both result runs above beat "just own the whole group" by a wide margin, which looked
convincing. A closer statistical check found the tools used to judge "is this margin real, or
could it be luck?" were actually asking a different, easier question the whole time — one that
almost any winning stock-picking strategy in a rising market would pass, whether or not the
picks were actually skillful. Once fixed to ask the right question: the margin over "own the
whole group" **is not statistically distinguishable from luck** (on the smaller 30-stock group:
about a 1-in-3 chance this margin is noise, not skill — nowhere near confident). Most of the
seven-year edge also turns out to come from a single year (2024) and a single stock (NVIDIA);
without either one, the margin disappears or reverses. The "choppy markets" and "one 7-year
stretch" catches above still stand and are now joined by this one. Bottom line: this idea has
**not** been shown to work — it needs either a longer/different test or to be set aside.

## What's needed before this goes any further
1. Tenzing reviews the economic reasoning above and signs off, amends it, or rejects it.
2. Tenzing reviews whether this looks like a real edge or a survivorship illusion, and
   finalizes the real cost assumptions being used.
3. Only after signing off: Tenzing sets up a real (but fake-money/paper) trading account and
   runs this idea for 2+ weeks before there's any further conversation about real money.
