# What To Do Right Now

*Check this page every week. This is the only page where "am I behind?" has an answer.
Last refreshed: 2026-09-14. The engineering side (the code, the data, the testing) is
caught up — the bottleneck right now is Tenzing's own sign-off.*

## 🟡 Tenzing — open items
1. **Sign off on Strategy 001 (momentum).**
   - The idea: buy the 10 stocks that have gone up the most over the last year, hold them a
     month, repeat. It's called "momentum."
   - It's already been tested, twice now (once on ~90 stocks, once on a cleaner list of 30) and
     it beat every baseline both times — see **Strategy Ideas → 001 Cross-Sectional Momentum**.
   - The job is NOT to check the math. It's to answer: *does this make economic sense? Do you
     believe the reason it works, or do you think it's a fluke?* Write an honest answer on
     that page, then say whether it should move to fake-money (paper) trading.
2. **Approve (or reject/edit) the 30-stock test list.** Cut the stock list from ~97
   down to a clean 30 well-known companies (Apple, Microsoft, JPMorgan, etc. — full list on
   the **Results So Far** page) to make testing faster and easier to reason about. This is
   the call to formally bless as final, per the role — see **Roles → Tenzing**.
3. **Give judgment on Strategy 001's result.** Is this a *real* edge, or is it an illusion
   caused by the fact that we only tested stocks that happened to survive and do well? Read
   the "Caveats" section on that page before answering.

## ✅ Engineering is caught up
- Built and tested the whole pipeline, cleaned the stock list to 30, and actually re-ran both
  test tools live on 2026-07-06 (results are real, not projected — see **Results So Far**).
- Left to do: get real (fake-money) trading account keys set up, and connect the two newer
  test tools to the automatic results log.

## Why this page matters
The code cannot approve a strategy. Only a human weighing "does this make sense" and "could
this be a fluke" can do that — see **Roles** for exactly why. Until Tenzing does the item
above, nothing advances, on purpose.
