# Results So Far (The Track Record)

*One row per real test. Newest first. Most rows say "no edge" — that's the system being
honest, not the system failing. We would rather know the truth than feel good.*

## How to read a row
- **Result (after costs, on unseen data)** — the only number that matters. Everything else is diagnosis.
- **vs. SPY** — what you'd have made just buying and holding the S&P 500 index over the same period. If we didn't beat this, active trading actively lost.
- **Verdict** — KILL / ITERATE (keep working on it) / ADVANCE (worth paper-trading). Never "trust me."

| Date | What was tested | Tested on | Result (net of costs) | vs. SPY / vs. baselines | Verdict |
|------|------------------|-----------|------------------------|--------------------------|---------|
| 2026-07-06 | Strategy 001 (momentum), re-run on a cleaner/smaller stock list | 30 stocks, 2019–2026 | **+309%** | Beat SPY (+180%), beat owning the whole group (+285%), beat random picks (+277%) | ITERATE → paper? |
| 2026-07-06 | Wide test of simple timing rules (moving averages, mean-reversion, trend) | 31 stocks × 3 strategies = 93 tests | **0 real edges found** | 10 "maybe," 83 dead on arrival | KILL (all) |
| 2026-07-05 | Strategy 001 (momentum), original run | ~90 stocks, 2019–2026 | **+972%** | Beat SPY (+180%), beat owning the whole group (+265%), beat random picks (+250%) | ITERATE → paper? |
| 2026-07-05 | Wide test of simple timing rules | ~100 stocks × 3 strategies = 309 tests | **0 real edges found** | 38 "maybe," 271 dead on arrival | KILL (all) |
| 2026-06-30 → 07-03 | Earlier wide tests of simple timing rules | 53 stocks | **0 real edges found** | Same story, smaller list | KILL (all) |

## The pattern, in plain English
Simple "buy when the price crosses a line" style strategies **do not work** on individual
stocks once you account for real trading costs and test them honestly — 0 survivors out of
over 700 attempts across three rounds of testing. That's actually the expected, textbook
outcome; if it were easy to beat the market with a simple rule, everyone would already be
doing it. The one idea that *has* survived every test so far is momentum (Strategy 001) —
picking baskets of winning stocks, not timing one stock's price — see the Strategy Ideas
section for the full writeup and its important caveats before getting excited.

## The current 30-stock test list
Cut down from ~97 stocks on 2026-07-06 for a cleaner, faster, easier-to-reason-about test
group (no penny stocks, no leveraged/risky ETFs). Pending Tenzing's formal approval.

**Tech:** Apple, Microsoft, Nvidia, Google, Amazon, Meta, Broadcom, Adobe, Salesforce, Oracle
**Financials:** JPMorgan, Bank of America, Goldman Sachs, Mastercard, Visa
**Healthcare:** UnitedHealth, Johnson & Johnson, Eli Lilly, AbbVie, Merck
**Consumer:** Walmart, Costco, Home Depot, Procter & Gamble, Coca-Cola, McDonald's, Nike
**Energy/Industrial:** ExxonMobil, Chevron, Caterpillar
**Benchmark:** SPY (the S&P 500 index — what we compare everything to)

## Standing expectations (so nobody is surprised)
- Simple single-stock timing strategies mostly die once you include real costs. This is normal.
- Options trading with naive strategies loses almost everything to fees/costs in our testing —
  which is exactly why we don't trade real options money yet.
