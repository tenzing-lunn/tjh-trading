# Thesis 001 — The Long-History Test (P1.2)

Home: [[PROJECT_PLAN]] · Task: [[plan/12-real-markets-plan]] **P1.2** · Engine: `long_history.py`
Data: `research_data/french/` (via `fetch_french.py`, gitignored — vendor terms)
Status: **Gate G1 criterion 1 — PASSES on the century. Read the caveats before believing it.**

---

## What this test is, and what it is *not*

Every other Thesis-001 result in this repo picks stocks **inside a universe we chose**
(`xsect.py` on 30 hand-picked names; `pit_panel.py` on the point-in-time S&P 500). Both
inherit the same doubt: maybe the "edge" is the universe, not the signal.

This test removes the universe entirely. Ken French publishes **10 portfolios formed on
prior 12-2 returns** — every NYSE/AMEX/Nasdaq name, sorted into deciles by trailing
12-month-skip-1-month return, rebalanced monthly, back to **January 1927**. The top decile
(`Hi PRIOR`) is the academic reference version of what we are trying to do. If momentum
does not beat the market *there*, over 99.6 years and thousands of names, nothing we build
on 30 tickers is going to rescue it.

**The series tested:** for each month, `active = Hi PRIOR − (Mkt-RF + RF)`, i.e. the top
decile's total return minus the total market return that month. Joined on the intersection
of the momentum-decile and FF3 date columns (**1927-01 → 2026-07, 1195 months**); nothing
padded, nothing imputed.

**This is not our strategy.** French's decile is value-weighted, holds hundreds of names,
rebalances at month-end with perfect execution and no capacity limit. Ours is a
concentrated top-10 equal-weight basket in a small account. The long history tells us
whether *the phenomenon* exists; it does not tell us that *our implementation* captures it.
Criterion 2 of Gate G1 (P1.4, the no-hindsight stock list) is the test of that, and it is
the one still failing (t = 1.17–1.26).

---

## Headline numbers (gross, before costs)

| | value |
|---|---|
| Window | 1927-01 → 2026-07 (1195 months, 99.6 years) |
| Mean active return | **+0.5605 %/month** = **+6.73 %/yr** |
| Std dev (monthly) | 3.56 % |
| **t-stat** | **5.44** (p < 0.0001) |
| Newey-West t (12 lags) | 5.38 — autocorrelation does not explain it |
| Annualized information ratio | 0.54 |
| Compounded | top decile ×5,486,583 vs market ×17,488 → **314× the market** |

That 314× is the number that seduces people. The rest of this document is the reasons to
discount it.

---

## Per-decade table (gross)

| Decade | n months | Mean monthly active % | Annualized active % | t-stat | Sum of active % | Share of total gain |
|---|---:|---:|---:|---:|---:|---:|
| 1927-29 (partial) | 36 | 1.142 | 13.71 | 1.83 | 41.1 | 6.1 % |
| 1930s | 120 | 0.228 | 2.74 | 0.49 | 27.4 | 4.1 % |
| 1940s | 120 | 0.712 | 8.55 | **2.40** | 85.5 | 12.8 % |
| 1950s | 120 | 0.568 | 6.82 | **2.80** | 68.2 | 10.2 % |
| 1960s | 120 | 1.074 | 12.88 | **3.61** | 128.8 | **19.2 %** |
| 1970s | 120 | 0.865 | 10.38 | **3.23** | 103.8 | 15.5 % |
| 1980s | 120 | 0.224 | 2.69 | 0.87 | 26.9 | 4.0 % |
| 1990s | 120 | 0.839 | 10.07 | **3.03** | 100.7 | 15.0 % |
| 2000s | 120 | 0.145 | 1.74 | 0.36 | 17.4 | 2.6 % |
| 2010s | 120 | 0.190 | 2.28 | 0.79 | 22.8 | 3.4 % |
| 2020s (to 2026-07) | 79 | 0.597 | 7.17 | 1.02 | 47.2 | 7.0 % |

*"Share of total gain" = that decade's summed active return ÷ the 669.8 pp full-history sum.*

**Largest single decade: the 1960s at 19.2 %** — nowhere near the 50 % that would fail Gate
G1. The gain is genuinely spread across the century: **every one of the 11 buckets is
positive**, and 5 of them clear t ≥ 2 on their own. This is the single strongest fact in the
whole Thesis-001 file, and it is the opposite of the one-year-wonder pattern that killed the
30-name result (where 156 % of the edge came from 2024 alone).

The net-of-estimated-cost table is the same table shifted down by 0.109 %/yr; the decade
t-stats move by at most 0.04 (e.g. 1960s 3.614 → 3.583). It is in the script output, not
reproduced here, because at our assumed cost level it carries no information.

**The decade pattern that should worry you:** the three weakest decades other than the 1930s
are the **1980s (t = 0.87), 2000s (t = 0.36) and 2010s (t = 0.79)** — i.e. most of the period
since the anomaly was published. See "Has it decayed?" below.

---

## Momentum crashes — what the data actually shows

Worst single active months over the century:

| Month | Active return |
|---|---:|
| 1932-07 | **−21.06 %** |
| 1932-08 | −20.97 % |
| 1932-11 | −16.18 % |
| **2026-07** | **−15.14 %** |
| 2000-11 | −14.26 % |
| 1938-06 | −13.66 % |
| 1978-10 | −12.12 % |
| 2009-04 | −10.30 % |
| 1933-04 | −10.23 % |
| 1966-10 | −10.07 % |

Worst drawdowns of the cumulative active path (arithmetic, in percentage points), and of
relative wealth (top decile ÷ market, compounded):

| Episode | Arithmetic active DD | Relative-wealth DD | Recovered |
|---|---:|---:|---|
| **1932-07 → 1933-07** | −61.6 pp | −41.3 % | 1937-03 (rel.) / 1943-05 (arith.) |
| 2008-07 → 2009-10 | −38.3 pp | −32.0 % | **2020-06 — eleven years** |
| 2000-03 → 2001-01 | −35.8 pp | −34.3 % | 2003-10 / 2005-09 |
| 2020-09 → 2022-01 | −35.0 pp | −30.3 % | 2024-06 / **2026-04** |
| 1983-07 → 1985-01 | −24.0 pp | −22.0 % | 1990-06 / 1991-08 |
| 1937-04 → 1939-03 | — | −32.4 % | 1943-05 |

Findings the literature gets right, and one it does not emphasize enough:

- **1932-33 is the worst momentum crash on record, and it is far worse than 2009.** From
  1932-06 to 1933-12 the top decile lost **53.3 pp** to the market, including back-to-back
  −21 % and −21 % months. The mechanism is the classic one: after a 1929-32 collapse the
  "winners" are defensive survivors and the "losers" are beaten-down high-beta wrecks; when
  the market violently turns, the losers rip and the winner portfolio is left behind.
- **2009 is real but second-tier for a long-only top decile.** Calendar 2009 cost −16.6 pp
  of active return, worst month 2009-04 at −10.3 %. The famous −80 % momentum-crash numbers
  in the literature are for the **long-short** (winners minus losers) factor; our long-only
  version does not short the losers, so it eats only half the crash. The *drawdown* from the
  2008-07 peak was −38 pp and took **until June 2020 to recover** — over a decade underwater
  versus just holding the market. That is the number a real investor would have had to sit
  through.
- **It just happened again, last month.** 2026-07 is the **4th-worst active month in 99
  years (−15.1 %)**, immediately after a violent run (Hi PRIOR returned +31.7 %, +20.0 %,
  +8.4 % in 2026-04/05/06). The 2020-09 → 2022-01 drawdown had only *just* recovered in
  2026-04. Anyone reading the 314× number should note that the strategy took a −15 % active
  hit in the most recent month of available data.
- **2020 was not a crash for this portfolio** (calendar-2020 active **+17.5 pp**); the pain
  came afterwards, in the 2020-09 → 2022-01 value/reopening rotation.

Momentum's return distribution is left-skewed by construction: many small wins, occasional
catastrophic reversals at market turning points. Nothing in this file argues that away.

---

## The after-cost estimate (and why it is the weakest section)

`costs.py`'s LIQUID-ETF regime is `spread_bps=3, slippage_bps=1, fixed_fee=0`, and
`cost_fraction` charges **half the spread plus slippage per unit of turnover** =
**2.5 bps per unit of turnover** (not 4). Our canonical `xsect.py` spec turns over
**435 %/yr**. Spread evenly:

```
drag = (4.35 / 12) × 2.5 bps = 0.91 bps/month = 0.109 %/yr
```

| | gross | net (estimated) |
|---|---:|---:|
| Mean active | +6.73 %/yr | **+6.62 %/yr** |
| t-stat | 5.44 | **5.35** |
| Newey-West t | 5.38 | 5.29 |

**Declare the assumptions loudly:**

1. **This is an estimate, not a backtest.** French does not publish the deciles' turnover,
   so the drag is imposed from *our* strategy's turnover, not the portfolio's own.
2. **435 %/yr is almost certainly too low for a monthly-rebalanced decile.** A top-decile
   12-2 portfolio commonly replaces most of its names each month (turnover plausibly
   1000–2000 %/yr). Sensitivity is below.
3. **2.5 bps is a 2020s number applied to 1927.** Before decimalization (2001) and before
   negotiated commissions (1975), realistic all-in round-trip costs on US equities were tens
   of basis points. This is the assumption that actually matters, and it is wrong for two
   thirds of the sample.

Sensitivity grid — net active %/yr and t-stat, across turnover × cost per unit turnover:

| Turnover | 2.5 bps (today) | 20 bps | 50 bps (pre-1975-ish) |
|---|---:|---:|---:|
| 200 %/yr | +6.68 / t=5.40 | +6.33 / t=5.11 | +5.73 / t=4.63 |
| **435 %/yr (our spec)** | **+6.62 / t=5.35** | +5.86 / t=4.73 | +4.55 / t=3.68 |
| 800 %/yr | +6.53 / t=5.28 | +5.13 / t=4.14 | +2.73 / t=2.20 |
| 1200 %/yr | +6.43 / t=5.20 | +4.33 / t=3.50 | +0.73 / t=0.59 |
| 2400 %/yr | +6.13 / t=4.95 | +1.93 / t=1.56 | **−5.27 / t=−4.26** |

Read that table honestly: **at modern costs the edge survives any plausible turnover
(t ≥ 4.95 everywhere in column 1). At historical costs and high turnover it does not exist
at all.** A large part of the century-long "momentum premium" was probably never harvestable
by anyone paying 1950s commissions. What makes it *potentially* tradeable today is precisely
that execution got ~20× cheaper — which is also the reason to expect the premium to be
arbitraged down, and the decade table says it has been.

---

## Has it decayed? (not asked by P1.2, but it changes the reading)

| Sub-period | n | Gross active %/yr | t |
|---|---:|---:|---:|
| Full (1927-01→) | 1195 | 6.73 | **5.44** |
| Post-1963 (CRSP-quality data) | 763 | 6.72 | **4.39** |
| Post-1993 (after Jegadeesh & Titman published) | 403 | 4.78 | **2.04** |
| Post-2000 | 319 | 3.29 | 1.20 |
| Post-2010 | 199 | 4.22 | 1.28 |

The premium is smaller and much less significant after publication, and **not significant at
all in the window any of us could actually have traded**. The century passes the bar; the
33 years since publication scrape it (t = 2.04); the 26 years since 2000 do not (t = 1.20). Some of that is just fewer months — 199 months at 4.22 %/yr
is not evidence of *absence*. But it means the honest sentence is "momentum was real, and
may still be real, at roughly half its historical size."

---

## Plain-English verdict

**Does the top momentum decile beat the market with t ≥ 2 overall? YES — overwhelmingly.**
Over 1195 months the top decile beat the total market by **+6.73 %/yr with t = 5.44** gross,
and **+6.62 %/yr with t = 5.35** after our estimated cost drag (t = 5.38 / 5.29 with
Newey-West standard errors). This is not marginal; it is one of the most statistically solid
facts in empirical finance, and it does not depend on any universe *we* chose.

**Does any single decade supply more than half the gain? NO.** The largest contributor is the
**1960s at 19.2 %** of the total. Every decade bucket is positive and five clear t ≥ 2
standalone. There is no one-year wonder here.

**Gate G1 criterion 1: PASS**, before and after estimated costs.

**But it does not mean go trade this, and here is the one-paragraph version of why.** The
century-long result is about *the phenomenon*, measured on a value-weighted, hundreds-of-names,
perfectly-executed academic portfolio — not about our concentrated 10-stock basket, which is
what criterion 2 (P1.4) tests and where the t-stat is still only 1.17–1.26. The after-cost
number here is an estimate imposed from outside, and the sensitivity grid shows that at
pre-decimalization trading costs with realistic decile turnover the premium disappears
entirely (t = 0.59 at 1200 %/yr × 50 bps) — so a large part of the 99-year record was never
actually harvestable. The premium has shrunk since publication (t = 2.04 post-1993,
t = 1.20 post-2000). And the tail is genuinely ugly: −53 pp in 1932-33, eleven years to
recover from the 2008-09 drawdown, and a **−15.1 % active month in 2026-07, the 4th worst in
99 years, in the most recent data we have.** The correct summary is: *momentum is real,
criterion 1 passes cleanly, and the remaining question — whether our specific implementation
captures any of it net of our costs — is exactly the question criterion 1 was never able to
answer.*

---

## Reproduce

```bash
python3 fetch_french.py      # LOCAL only (internet); fills research_data/french/
python3 long_history.py      # prints every number in this document
```

Open items for [[research/audits/phase1]] (P1.7, Fable):
- Confirm `fetch_french.py` takes the **value-weighted** block of
  `10_Portfolios_Prior_12_2_CSV.zip` (it parses the first monthly block, which should be
  "Average Value Weighted Returns — Monthly"). If it is the equal-weighted block instead,
  every level in this document shifts (the sign of the verdict almost certainly does not).
- Check the market leg: total market = `Mkt-RF + RF`, not `Mkt-RF` alone. Using the excess
  return by mistake would inflate the active return by ~3.2 %/yr.
- Re-derive t = 5.44 and the 19.2 % decade share independently.
