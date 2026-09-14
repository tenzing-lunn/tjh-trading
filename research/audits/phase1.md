# Phase 1 red-team audit (P1.7)

Home: [[PROJECT_PLAN]] · Plan: [[plan/12-real-markets-plan]] row **P1.7** · Gate: **G1**
Scope: P1.2 (`long_history.py`, commit `65f4d2b`), P1.4 (`fetch_membership.py` /
`fetch_pit_prices.py` / `pit_panel.py`, `9d83945`), P1.5 (`xsect.py` MTUM row, `cc78012`),
P1.6 (`cost_sweep.py`, `afc646f`), plus the cross-cutting multiple-testing question.

*Written 2026-09-14 (Fable, adversarial). Every number below was re-derived from raw inputs or
by re-running the code with a change I control, not by reading the author's output. Verdicts:
**CONFIRMED** = I reproduced it independently; **WRONG** = the stated claim or number is
incorrect (each says whether the conclusion survives); **UNCLEAR** = cannot be settled with what
is on disk today. Scratch scripts lived in the session scratchpad and were not committed; each
check says what was done so it can be redone in ten lines.*

**One-paragraph result.** P1.2 holds exactly. P1.4's *conclusion* (momentum vs the point-in-time
EW universe fails t ≥ 2) holds, but its *numbers* are wrong in three separable ways — a
one-month date misalignment in the "same dates" comparison, a data-join artefact that hands the
EW-eligible leg a **+12.3 % single day** (`SW`, 2024-07-05), and a corrupt vendor series
(`PARA`) — and it rests on 59 % span coverage with a tenure-biased exclusion. Corrected, the
survivorship gap is ~**+135–143 pp** (not +103–105) and momentum's active t is **1.14–1.45**
on 2009–2026 and **1.72–1.78** on 2019–2026: still below 2 everywhere. P1.5's deliverable was
not delivered (no `realdata/mtum.csv`, so the row never prints); I fetched MTUM independently
and report the number. P1.6's numbers reproduce but its cost labels are off by 2× and it reads
the sign of a statistically insignificant margin — the exact error P0.2 catalogued. Nothing here
changes the standing verdict (**Thesis 001 UNPROVEN**) or the G1 outcome (criterion 1 passes,
criterion 2 fails).

---

## P1.2 — Long-history momentum test (Ken French, 1927–2026)

### Item 1 — Does `fetch_french.py` take the **value-weighted** block? — **CONFIRMED**
Downloaded `10_Portfolios_Prior_12_2_CSV.zip` and `F-F_Research_Data_Factors_CSV.zip` myself
(2026-09-14, "202607 CRSP database" build). Block titles in the raw file, in order: line 9
**"Value Weight Returns -- Monthly"**, line 1208 "Average Equal Weighted Returns -- Monthly",
then the annual and firm-count blocks. The parser's header-finder stops at the first
comma-leading short line, which is line 10 (`,Lo PRIOR,…,Hi PRIOR`) directly under the VW
title, and stops at the first blank line (1206). I parsed the VW block independently and
compared to `research_data/french/10_portfolios_momentum_monthly.csv`: **1195 rows, max
absolute difference 0.0** on `Hi PRIOR`. Against the EW block the max difference is 34.98, so
the repo file is unambiguously the VW one. No `-99.99`/`-999` sentinels in either used column.
(For scale: had the EW block been used, the active return would read 9.25 %/yr, t = 6.62.)

### Item 2 — Market leg is `Mkt-RF + RF` (total return)? — **CONFIRMED**
`long_history.py:40`: `df['mkt'] = (df['Mkt-RF'] + df['RF']) / 100.0`. Re-derived: with the
total market the mean active return is 6.73 %/yr; with `Mkt-RF` alone it would be 9.97 %/yr
(t = 8.03). Mean RF over the window is 3.24 %/yr, matching the "~3.2 %/yr" the author warned
about. The right leg was used.

### Item 3 — Re-derive t = 5.44, the decade table, the after-cost estimate — **CONFIRMED**
From the raw zips, joined on the date intersection (1927-01 → 2026-07, n = 1195):

| statistic | author | mine |
|---|---:|---:|
| mean active | +0.5605 %/mo, +6.73 %/yr | +0.5605 %/mo, +6.73 %/yr |
| t (iid) | 5.44 | **5.44** |
| Newey–West(12) t | 5.38 | **5.38** |
| compounded ratio | 313.7× | 313.7× |
| net (435 %/yr × 2.5 bps) | +6.62 %/yr, t = 5.35, NW 5.29 | +6.62, **5.35**, 5.29 |
| largest decade share | 1960s 19.2 % | **1960s 19.2 %** |
| post-1993 / post-2000 / post-2010 t | 2.04 / 1.20 / 1.28 | 2.04 / 1.20 / 1.28 |

All 11 decade rows match to three decimals. Cost per unit turnover: `costs.py` charges
`0.5·spread + slippage` = 0.5·3 + 1 = **2.5 bps**; drag = 4.35/12 × 2.5 bps = 0.906 bps/month
= 0.109 %/yr. I also verified the **435 %/yr** input is real: on the 30-name `xsect` panel the
realised momentum turnover (`res['turnover'].sum()/years`, one-way notional) is **434 %/yr**.

Two things I added that the author did not run, both of which make the pass *stronger*:
- **Metric independence of criterion 1.** "Share of the gain" is defined by the author as the
  decade's arithmetic sum ÷ the total sum. Under the alternative — share of cumulative log
  relative wealth, `Σ[log(1+hi) − log(1+mkt)]` — the largest decade is still the 1960s at
  **20.3 %**. The 50 % bar is not sensitive to which definition was picked.
- **A stricter test than "beats the market".** Raw active return vs the market is not alpha
  if the top decile carries beta ≠ 1. CAPM regression of `Hi − RF` on `Mkt − RF`: beta 1.029,
  **alpha 6.49 %/yr, t = 5.21 (HAC-12 t = 5.35)**. The premium is not a beta artefact.

### Item 4 — Is the after-cost estimate honest, and is 435 %/yr used correctly? — **CONFIRMED**
The document says "This is an estimate, not a backtest" in the section title and in three
numbered assumptions, and its sensitivity grid puts the *unflattering* cells (t = 0.59 at
1200 %/yr × 50 bps; t = −4.26 at 2400 %/yr × 50 bps) in the writeup. The 435 %/yr figure is
applied as `TURNOVER_YR/12 × cost_fraction(1.0)` per month, which is the correct reading of the
plan's spec ("using our turnover (435 %/yr) and 3/1 bps"). Caveat the author already states
and I endorse: 435 %/yr is *our* 10-of-30 turnover; French's decile of hundreds of names with
NYSE breakpoints turns over far more, so the "net" column is a lower bound on the drag, not a
backtest of the decile.

### Item 5 — Lookahead in the join / cherry-picked dates? — **CONFIRMED (none found)**
Both files are keyed `YYYYMM` and parsed to the first of the month; both are *realised* returns
for month t (French forms the portfolio at end of t−1 from returns t−12…t−2), so the join is
contemporaneous and cannot leak. Inner join, nothing padded: FF3 starts 1926-07, the deciles
1927-01, hence n = 1195. The full available history is used; the sub-period cut points (1963,
1993, 2000, 2010) are the standard ones in the literature and are reported *against* the
thesis (post-2000 t = 1.20). No date choice flatters the result.

### P1.2 verdict
**Gate G1 criterion 1 PASSES as stated** (t ≥ 2 overall gross and net; no decade > 50 %).
Everything in `research/theses/001-long-history.md` reproduces to the printed precision. The
author's own caveats — value-weighted hundreds-of-names portfolio ≠ our 10-stock basket;
post-publication decay; 2026-07 was the 4th-worst active month on record — are correct and
should travel with the pass.

---

## P1.4 — Point-in-time, no-hindsight S&P 500 universe

### Item 1 — No lookahead in membership / eligibility — **CONFIRMED (for what the test covers)**
`pit_panel.build` sets `eligible[t, company]` from `calendar >= start_date & calendar <
end_date` per span, zeroes it before `window_start`, and `xsect.target_weights` /
`_ew_weights` consult only `eligible.loc[t]` at rebalance t; `held = weights.shift(1)` is
unchanged in the engine. Acceptance test 1 asserts, over the actual weight frames under both
patches, zero mask-outside-span, zero held-before-start, zero selected-outside-span; I re-ran
it and it passes. Momentum lookback correctly uses pre-membership price history (Tiingo series
start at IPO, `HISTORY_START = 1990`), so the *signal* is legitimate and only *selection* is
masked, as the design doc §3.5 requires. Spot checks of the spine: TSLA start 2020-12-21, NVDA
2001-11-30, GOOGL 2006-04-03, FB→META 2013-12-23/2022-06-09, SIVB/FRC/SBNY class B with the
FDIC receivership dates — all correct. Membership date density (13–38 distinct change dates
per year) is consistent with a genuine change log, not sparse snapshots. **Residual, not
testable here:** the fja05680 spine's pre-2019 provenance is second-hand (design doc §1.1); test
1 proves the code respects `membership.csv`, not that `membership.csv` is right.

### Item 2 — Delisting haircut only on the LAST span — **CONFIRMED**
`pit_panel.py:146,155,166`: `is_last = (i == len(spans) − 1)` gates both the class-B Shumway
haircut and the pessimistic `−100 %` for missing A/B exits; a single `terminal` tuple is
applied once after the span loop. In the current data **zero haircuts are actually applied**
(pessimistic `patches` = `missing_bkr: 3, missing_acq_zeroed: 29`, no `haircut_bkr`): the only
priced class-B span is PCG, whose series continues (correctly no haircut); SIVB/FRC/MTLQQ are
absent from Tiingo (zeroed at exit under pessimistic); SBNY is still `pending_fetch`. So the
−30 %/−55 % constants are wired correctly but have never fired.

### Item 3 — `pending_fetch` excluded, not imputed as flat — **CONFIRMED, but see Finding C**
`pit_panel.py:139-141`: a span whose symbol has no manifest entry is counted
`pending_fetch_excluded` and `continue`s *before* `e |= in_span`, so it is never eligible and
never filled. 290 spans (32 % of the window) are excluded this way.

### Item 4 — Run `pit_panel.py`; TEST 4 byte-identical to the old path — **CONFIRMED**
Ran it. TEST 4: `target_weights`/`_ew_weights` with `eligible=None` `.equals()` the no-arg
call → YES; momentum **309.4 %**, EW **284.5 %**, active t **0.34**, NW **0.41** — identical to
the thesis and to a fresh `python3 xsect.py`. Nothing in the P1.4 engine change touched the
30-name path.

### Item 5 — Secrets and vendor data out of git — **CONFIRMED**
`.gitignore` ignores `.env`, `research_data/*` (re-opening only `universe/membership.csv` and
`universe/renames.csv`), `realdata/`, `data_cache/`; `git check-ignore` confirms
`research_data/pit_prices/*` and `research_data/french/*` are ignored. `git ls-files` shows
only the two membership CSVs, the fetch scripts and `.env.example` under those names.
`git log --all --full-history -- "*tiingo*"` → empty; `git log --all --diff-filter=A` never
added anything under `pit_prices/`, `french/` or a `.env`. `.env.example`'s `TIINGO_API_KEY`
value is a 29-character placeholder; the local `.env` holds a 40-character value (a real key
is present locally, is untracked, and was not printed anywhere in this audit). `fetch_pit_prices.py`
reads it via `os.environ` and never logs it. Clean.

### Findings the checklist did not ask for (this is where the errors are)

**Finding A — TEST 5 "same dates" is misaligned by one month. — WRONG (minor; conclusion unchanged)**
TEST 5 zeroes eligibility before `lo = res.index[0] = 2019-08-01`, so the 2019-07-31 rebalance
sees an empty universe and the PIT legs first hold on **2019-09-03 (1717 bars, 83 months)**
while the 30-name legs run from **2019-08-01 (1739 bars, 84 months)**. The 30-name EW lost
−2.01 % over the unmatched month. Allowing the 2019-07-31 rebalance (eligible from that date)
gives, as committed vs aligned: PIT EW 181.1 % → **173.0 %**, bias +103.4 → **+111.5 pp**,
active t 1.38 → **1.44** (optimistic; pessimistic 179.1 → 170.5 %, +105.4 → +114.0 pp, 1.39 →
1.45). The committed numbers *understate* both the bias and momentum's edge; no sign changes.

**Finding B — A join artefact hands the EW-eligible leg +12.3 % in one day. — WRONG (material to the numbers; conclusion unchanged)**
Scanning every *held* (date, name) cell for |daily return| > 40 % turned up 37 EW cells; 36 are
real (AIG, FITB, CBRE in March 2009; NCLH/AAL in 2020; …) or small. One is not: **`SW`
2024-07-05, +5051 %**, held by the EW leg at weight 0.0024 → **+12.29 % contribution to the EW
leg that day**, followed by −98 % the next day at 1/50th the exposure. Root cause, a chain of
three problems:
1. `research_data/pit_prices/WRK.csv` contains **one row** (2024-07-05, 51.51) although
   Tiingo's manifest lists WRK 2015-06-24 → 2024-07-05. The manifest still says `fetched`.
   `fetch_pit_prices` never sanity-checks row count against the vendor's own span.
2. `build_companies` assigns one `price_symbol` per company (WRK for the WRK→SW rename), so the
   post-rename SW era is never fetched even though Tiingo has `SW` from 2024-07-08. The SW span
   therefore has no prices → status `missing` → **flat-filled at 1.0** on both sides of the
   lone real 51.51 bar (1.0 → 51.51 → 1.0). Same structural hole for VTRS (MYL series ends
   2020-11-19, VTRS never fetched) and PSKY (below).
3. The `missing` flat-fill writes `1.0` into a column wherever it is NaN, with no guard against
   sitting next to a real bar.
Neutralising only that seam: full-window PIT EW **1386.7 % → 1228.0 %** (CAGR 16.6 → 15.8 %),
active t **1.17 → 1.39** (pessimistic 1.26 → 1.48); 2019–2026 aligned EW 173.0 → 143.9 %,
bias **+140.6 pp**, t **1.76**. Momentum's own figures are untouched (it never held SW).

**Finding C — Two more vendor-data faults in held names. — WRONG (small individually)**
- **`PARA` (company key `PSKY`) is corrupt end to end**: Tiingo's adjClose reads 83,754 in
  2021-02, ~86,000 in 2023, 57 on 2025-08-06, and **1.0** on the last bar; ten days with
  |return| > 30 % in 2021–2026 (Paramount had perhaps one). The column is held by EW throughout.
- **`TMUS` 2013-05-01: +108 %** — the MetroPCS 1-for-2 reverse split on the merger day is not
  adjusted in the fetched series; held by EW at weight 0.0025.
- **Fetch integrity is worse than the manifest says.** 11 of 500 `fetched` symbols have < 50 %
  of the rows Tiingo's own span implies; several (APC, STI, CA, MON, DNB, DOW, SPLS, FTR) have
  a file whose *first* date is after the vendor's stated *end* date — i.e. Tiingo returned a
  **different, later company under a reused ticker** and the manifest recorded it as a
  success. `pit_panel` then finds no prices inside the old company's span and flat-fills it.
- **`missing` ≠ "dead name".** The doc reads the 75 `missing` spans as "the dead names the
  §2.3 rules impute". `EQR` — a live S&P 500 REIT — is `missing_no_tiingo_data` (no manifest
  row survives the `assetType in {Stock, ETF}` / `startDate` filter) and is held **flat at 0 %
  for all 211 months**. `HCP` (now DOC; the HCP→PEAK link is not in the rename map) is flat
  for 130 months. Flat-filled names are **3.9 % of all eligible name-months** (14.4 % on
  2009-01-30), top contributors EQR 211, STI 131, PSKY 131, HCP 130, APC 127, CA 118, MON 113.

**Finding D — The optimistic/pessimistic pair does not bracket the t-stat. — WRONG (framing)**
Both patches change only what the EW leg absorbs (0 % or −100 % for unpriced names); momentum
returns **2637.1 % under both** because it never selects a flat, zero-score name. Every flat
name therefore lowers EW and *raises* momentum's edge — so "optimistic" is in fact the
momentum-*favourable* bracket for the gated quantity, and "pessimistic" is more so. The
missing bracket is the **neutral imputation** (an unpriced name is assumed to earn the basket's
own return, i.e. is dropped from EW that month). With the surgical clean of Finding B/C applied
and flat names dropped from EW: full-window EW **1444.8 %**, active t **1.14** (NW 1.21) —
*below* the committed 1.17. The honest statement is a three-way range, not "does not flip
between the brackets": full window **t = 1.14 – 1.45**, 2019–2026 aligned **t = 1.72 – 1.78**.
All below 2; the conclusion survives, the phrasing does not.

**Finding E — Coverage is 59 % and the exclusion is tenure-biased, not random. — UNCLEAR**
Fetch order is "most eligible months first", so the 280 pending companies have median tenure
**51 months vs 212** for the fetched ones. 115 of them are *currently active* members, and
**108 of those 115 first joined in 2018–2026** (ABNB, ANET, APP, AXON, BX, COIN, CRWD, DASH,
DDOG, DELL, …). The 2019–2026 "point-in-time universe" is therefore the index's **pre-2018
cohort**: 412 eligible names in 2024-06 and 391 in 2026-06 against a true ~500. The other 165
pending are short-tenured exits (80 C, 68 A, 16 D, 1 B — includes SBNY). Excluding recent
additions (index-inclusion winners) and quick exits (losers) pushes EW in opposite directions;
I cannot sign the net effect. Every P1.4 number is provisional until the remaining ~290 spans
are fetched and the run repeated. The doc says this; the headline in `plan/12` does not carry
the caveat forward.

**Finding F — TEST 2 (EW vs RSP) is loose, but decomposable. — UNCLEAR → CONFIRMED-ish**
EW-eligible CAGR 16.60 % vs RSP 14.77 %, +1.83 pp/yr, labelled "within a few points". After the
SW seam alone the gap is **+1.08 pp/yr**. Of the remainder, RSP's 0.20 % expense ratio and the
engine's mechanics (see "Out-of-scope observation") plausibly account for most of what is left.
The test is directionally reassuring but its ±4 pp tolerance is wide enough to have passed a
+12 %-day artefact, so it is not a sufficient guard.

### Corrected P1.4 numbers (my re-runs; the author's code unchanged except the stated patch)

| run | PIT mom | PIT EW | active t | NW t |
|---|---:|---:|---:|---:|
| 2009-02 → 2026-09, as committed (opt / pess) | 2637 % | 1387 % / 1283 % | 1.17 / 1.26 | 1.26 / 1.36 |
| … + surgical clean (SW seam, PSKY column, TMUS split) | 2637 % | 1256 % / 1161 % | **1.36 / 1.45** | 1.46 / 1.57 |
| … + neutral imputation (flat names out of EW) | 2631 % | 1445 % | **1.14** | 1.21 |
| 2019-08 → 2026-07 **aligned**, as committed (opt / pess) | 448 % | 173 % / 171 % | 1.44 / 1.45 | 1.43 / 1.45 |
| … + surgical clean | 448 % | 148 % / 146 % | **1.73 / 1.75** | 1.72 / 1.74 |
| … + neutral imputation | 448 % | 150 % | 1.72 | 1.70 |
| **measured survivorship + winner-selection bias** (30-name EW 284.5 % − PIT EW, aligned, cleaned) | | | **+135 to +139 pp** | (committed: +103/+105) |

### P1.4 verdict
**Criterion 2 FAILS, as the author concluded**, under every correction I could construct
(t ≤ 1.45 on the long window, ≤ 1.78 on 2019–2026). But `plan/12`'s headline sentence —
"+103 to +105 pp … t rises from 0.34 to 1.17–1.26 … does not flip between brackets" — should
be restated as: *bias ≈ +135–143 pp; t ≈ 1.1–1.5 (2009–26) / 1.7–1.8 (2019–26); provisional on
59 % coverage; brackets do not bound the t-stat.* $0 fixes, in priority order: (1) validate
each fetched file against Tiingo's span and refuse files whose first date is after the vendor's
end date (ticker reuse); (2) fetch every symbol in a rename chain and stitch, or at minimum
mark the post-rename era `pending` rather than `missing`; (3) forbid a `1.0` fill bar from
touching a real bar (NaN the seam) and add a held-cell |return| > 60 % scan to the acceptance
tests; (4) drop series whose adjClose max/min ratio is absurd (PARA); (5) open TEST 5's
eligibility from the rebalance *before* `lo`; (6) add the neutral-imputation run to the bracket;
(7) look at why EQR is absent from `supported_tickers()` after the asset-type filter.

---

## P1.5 — MTUM baseline

### Code: same window, fair comparison? — **CONFIRMED**
`xsect.py:390-398` mirrors the SPY block exactly: `reindex(window).dropna()` onto the live
momentum window, static long position, `run_backtest` at `ETF_COST`. `fetch_universe.py` uses
`yf.download(..., auto_adjust=True)`, so the close is split- *and dividend-*adjusted — a total-
return comparison. I confirmed the method by pulling SPY from Yahoo's chart API with `adjclose`
and reproducing the repo's **179.7 %** exactly over 2019-08-01 → 2026-07-02 (price-only would be
152.5 %, so dividends matter ~27 pp here).

### Deliverable: "MTUM row appears with same-window return, Sharpe and max drawdown" — **WRONG (not met)**
`realdata/mtum.csv` does not exist (the commit message says so). `python3 xsect.py` prints no
MTUM row. As the repo stands, **G1 criterion 3 cannot be read from any committed output.** The
fix is one local `python3 fetch_universe.py`.

### The number, independently (Yahoo `adjclose`, same window, same `run_backtest`/`CostModel(3,1)`) — for the humans
| leg, 2019-08-01 → 2026-07-02 | total | CAGR | Sharpe | max DD |
|---|---:|---:|---:|---:|
| **hold MTUM (total return)** | **+183.4 %** | 16.3 % | 0.75 | −34.1 % |
| hold SPY | +179.7 % | 16.1 % | 0.85 | −33.7 % |
| 30-name momentum top-10 (survivorship-inflated) | +309.4 % | 22.7 % | 0.99 | −30.3 % |
| 30-name EW (survivorship-inflated) | +284.5 % | 21.6 % | 1.11 | −30.9 % |
| PIT momentum top-10 (aligned, provisional) | +447.7 % | 28.2 % | 0.91 | −37.6 % |
| PIT EW (aligned, cleaned) | ~+148 % | | | |

Read honestly: on this window MTUM barely beat SPY (+3.7 pp over seven years, lower Sharpe).
Our DIY basket is "not clearly worse" than MTUM on every row — but the two DIY rows that beat it
are the survivorship-inflated one and the provisional one, whereas MTUM is the only live,
cost-net, survivorship-free track record in the table. Criterion 3 is passable on the evidence;
it is not a strong pass. Caveat to record: MTUM's return already nets its 0.15 % expense ratio
and quarterly-rebalance costs; ours nets 2.5 bps per unit turnover and nothing else.

---

## P1.6 — Cost-sensitivity sweep

### Turnover held fixed while cost varies? — **CONFIRMED**
`cost_sweep.py:32-33` builds `mom_weights` and `ew_weights_obj` once, before the loop; only
`CostModel` changes. Turnover is cost-independent by construction. All four printed rows
reproduce (310.6 / 306.3 / 297.3 / 282.6 % vs EW 284.5 %).

### Cost labels — **WRONG (2× mislabelled)**
The sweep sets `spread_bps = level, slippage_bps = 0`, and `costs.py` charges half the spread,
so the effective cost per unit of one-way turnover is **half the printed label**: "3 bps" =
1.5 bps/unit (the canonical 3/1 regime is 2.5), "10" = 5, "25" = 12.5, **"50 bps" = 25 bps per
unit**. The script's own header says this; the thesis writeup then reports "turns negative at
50 bps" without the halving, labels the first row "3 bps (0/3 bps split)" (it is 3/0), and its
prose glosses the 10 bps row as "0.5 × 20 bps spread", which contradicts the table it sits
under. Interpolated breakeven from my re-run at 1.5/5/12.5/20/22.5/25/50 bps per unit:
**≈ 23.4 bps per unit one-way turnover, i.e. a 47 bps full spread with zero slippage.**
Plausibility check: momentum's realised turnover is 434 %/yr, so each extra 1 bp/unit costs
0.043 %/yr, and going 1.5 → 25 bps/unit costs ~1.0 %/yr, which on a ~4× equity path over 6.9
years is ~25 pp of total return — matching the 26.2 → −1.8 pp margin collapse. The arithmetic is
right; the labels are not.

### Interpretation — **WRONG (sign of an insignificant margin)**
The sweep reports only the *sign* of the total-return margin ("Beats EW? YES/NO"). The margin's
monthly active t is **0.36 / 0.31 / 0.22 / 0.06** across the four levels (NW 0.43 → 0.07) — never
close to 2. "Momentum's edge over EW persists through 25 bps" describes the zero-crossing of a
quantity that is statistically zero at every level; it is the point-comparison error
`research/audits/2026-09-gates.md` §4.3 identified, reintroduced by a Phase-1 task. The useful
output of this sweep is "the edge is not distinguishable from zero at any cost level tested",
not a breakeven. Also note the EW leg is charged **0 %/yr** turnover at every level (see below),
so the sweep is "momentum pays, EW is free"; at 25 bps/unit a real monthly EW rebalance of 30
names would cost of order 0.1 %/yr — small, but the asymmetry should be stated.

---

## Multiple testing / data snooping (all four tasks + prior Phase 0)

| choice | when made | before or after seeing real-data results? | verdict |
|---|---|---|---|
| Canonical spec 12-1 / monthly / top-10 / EW / long-only | thesis 001, before `xsect.py` ran (2026-07-03) | before; taken from the literature; sweep neighbours reported as sensitivity, never selected | **CONFIRMED** clean |
| **Universe 97 → 30 (2026-07-06)** | decision log 2026-07-06 | **after** the ~97-name run (+972 %) — the 30 "megacaps across 6 sectors" were chosen knowing which names had won 2019–2026 | **UNCLEAR / documented**: hindsight-tainted by construction, but the change moved the result *against* the thesis (t 1.65 → 0.34) and P1.4 exists precisely to replace it. Not a snooped-for-a-win choice; still not a pre-registered list. |
| G1 criteria (t ≥ 2; no decade > 50 %; MTUM; audit) | plan/12, 2026-09-13 | written *after* the 30-name t = 0.34 was known but *before* P1.2/P1.4/P1.5 ran | **CONFIRMED** for P1.2/P1.4/P1.5; the thresholds were not tuned to those results |
| P1.2 window (full 1927→), decade buckets, sub-period cuts, cost grid | P1.2 | fixed by data availability / literature; unflattering sub-periods reported | **CONFIRMED** clean |
| P1.2 "share of gain" metric (arithmetic sum) | P1.2, not pre-specified | after; but the alternative metric gives 20.3 %, same decade | **CONFIRMED** immaterial |
| P1.4 window 2009→, Shumway constants, opt/pess pair | P1.3 design doc, before any PIT run | before; chosen on coverage tables, not results | **CONFIRMED** clean |
| P1.4 hand rename/exit tables, "ESV→VAL not joined" | during P1.4 build | data-cleaning decisions made while looking at which names were missing, not at returns | **CONFIRMED** acceptable, auditable via `source` column |
| P1.4 fetch order (longest tenure first) | P1.3 §6.2 | before; but it makes the *interim* universe non-random (Finding E) | **UNCLEAR** until coverage is complete |
| P1.6 cost levels 3/10/25/50 | plan/12 | before | clean; the *labels* are the problem, not the choice |

No parameter, window or universe in Phase 1 was chosen after seeing the Phase-1 result it
feeds. The one hindsight-tainted object in the whole chain is the 30-name universe, which is
already flagged in three places and is the thing P1.4 replaces.

---

## Out-of-scope observation (pre-existing engine behaviour, affects every panel leg)
`xsect.run_panel` computes `gross = (weights.shift(1) × rets).sum(axis=1)` with target weights
forward-filled daily and charges cost only on *changes in target weights*. That is a portfolio
**rebalanced to target every day at zero cost**, not one that drifts between month-ends: the
EW leg's realised turnover is literally **0 %/yr** (`trades = 0` in the `xsect` table) although
a real equal-weight book must trade every month to stay equal-weight. The daily-rebalance
premium it earns is a plausible piece of the EW-vs-RSP gap (Finding F) and of the P1.6
asymmetry. It is symmetric across the momentum and EW legs in the sense that both get it, so it
does not obviously bias the active t; it does mean "net of costs on full turnover" overstates
how much cost is being modelled. Predates Phase 1; noting it for whoever owns the engine.

---

## Summary

**Items marked WRONG (6):** P1.4-A TEST 5 window misalignment (one month; conclusion unchanged) ·
P1.4-B/C the SW join artefact plus the PARA and TMUS series faults and the truncated/reused-
ticker fetches that the manifest calls `fetched` (headline bias and t-stat mis-stated; conclusion
unchanged) · P1.4-D "verdict does not flip between the brackets" (the brackets do not bound the
t-stat; neutral imputation gives t = 1.14) · P1.4-C's reading of `missing` as "dead names" (EQR is
live) · P1.5 deliverable not produced (no MTUM row exists anywhere) · P1.6 cost labels off by 2×
and a breakeven read off an insignificant margin.
**UNCLEAR (2):** P1.4 coverage (59 %, tenure-biased exclusion of 2018+ additions) and the
hindsight-chosen 30-name universe (already superseded by P1.4).
**CONFIRMED:** every P1.2 number and both of its self-flagged open items; P1.4's lookahead
guard, last-span haircut logic, pending-fetch exclusion, TEST 4 reproduction, and git hygiene;
P1.5's code; P1.6's arithmetic and fixed-turnover design.

**Does anything change the standing verdict that Thesis 001 is UNPROVEN?** No. Every
correction I could construct leaves momentum's edge over the honest universe at t ≤ 1.8 on the
window where it is strongest and t ≤ 1.5 on the long window, and the corrections mostly move
in momentum's *favour* (the committed numbers understate both the survivorship bias and the
edge). Momentum is real as a century-long phenomenon (P1.2) and unproven as our 10-stock
implementation (P1.4). That was the verdict before this audit; it is the verdict after it.

**Gate G1, criterion by criterion:**
1. **Long history — PASS, confirmed exactly** (t = 5.44 gross / 5.35 net; stricter CAPM alpha
   t = 5.21; max decade 19.2 % under the author's metric, 20.3 % under mine).
2. **No-hindsight list — FAIL, confirmed**, but the numbers quoted in `plan/12` should be
   replaced with the corrected range (bias +135–143 pp; t 1.14–1.45 on 2009–26, 1.72–1.78 on
   2019–26) and marked provisional until the Tiingo fetch completes and the fetch/join bugs
   above are fixed. A re-run after those fixes could move t either way; it would need to move
   from ~1.4 to ≥ 2 on the long window to change the outcome, which the data so far does not
   suggest.
3. **MTUM — cannot be read from the repo; on my independent number (MTUM +183.4 %, Sharpe 0.75)
   our version is not clearly worse.** Weak pass, pending a local `fetch_universe.py` so the row
   actually prints, and with the caveat that the DIY rows it beats are inflated or provisional.
4. **This audit** — errors found, none flips a conclusion. The G1 sheet should record criterion 2
   as the failing one, with the corrected numbers, and the fix list from the P1.4 verdict as
   the $0 work that precedes any re-test.
