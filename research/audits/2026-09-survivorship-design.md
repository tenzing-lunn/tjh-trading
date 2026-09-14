# P1.3 — A stock universe without hindsight (design, not code)

Home: [[PROJECT_PLAN]] · Plan: [[plan/12-real-markets-plan]] (rows P1.3 → P1.4 → G1) · Thesis: [[research/theses/001-cross-sectional-momentum]]

*Written 2026-09-14 (Fable, P1.3). This is a design/proposal document. Nothing here is
implemented; P1.4 (Opus) builds it. Every number below that came from a live check is marked
with the date it was checked; every claim I could not verify from the sandbox is marked
**UNVERIFIED** or **needs a human**.*

---

## 0. The problem, stated precisely

`fetch_universe.py` hard-codes 30 tickers chosen in 2026. That list has **two** hindsight
biases, and the second is worse than the one we usually name:

1. **Survivorship.** Every name still trades in 2026. Anything that went bankrupt, was bought,
   or delisted between 2019 and 2026 cannot be in the list. Classic.
2. **Winner selection.** The list is not "stocks that survived"; it is "the 30 biggest,
   most-liquid megacaps *as of 2026*". NVDA, LLY, AVGO, META, COST are in it *because* they
   won 2019–2026. This is stronger than survivorship: we pre-selected the winners of the
   very window we then backtest.

Both inflate every long-only row in `xsect.py`. The Thesis-001 writeup already says "beating
EW-universe is the bar that matters" as a partial defence, and it *is* partial: both legs of
momentum-vs-EW are inflated, but not equally, and the direction of the *relative* bias is
genuinely ambiguous —

- Dead and dropped names are usually low-momentum in their final months. Momentum top-10
  rarely holds them; EW always does. Restoring them would drag EW down more than momentum,
  which would *help* momentum's margin.
- But momentum also concentrates into names that later crash (2007 financials, 2021
  high-flyers) and misses junk rallies (2009). Restoring the point-in-time crowd of
  eventual losers that were *winners at the time* would *hurt* it.

So we cannot argue our way to the sign of the bias. We have to rebuild the universe as it
was and rerun. That is what this document designs.

**The target artefact:** a table `eligible[date, ticker] ∈ {True, False}` = "was this stock a
member of a broad, liquid, *rules-based* US universe on this date, as known on that date",
plus a price panel that includes every ticker that was ever eligible, through its death.

**Why the S&P 500 specifically.** We need a universe whose historical membership is
*publicly recorded* for free. "All US common stocks with market cap > X and ADV > Y" is the
academically cleaner universe, but reconstructing point-in-time caps/ADV for dead stocks is
exactly the data we cannot get free. S&P 500 membership is the only broad-liquid US universe
with a free, dated change log. It imports S&P's own selection rules (see §3.5) — an accepted
cost.

---

## 1. Free sources for historical S&P 500 membership

All three were checked live on 2026-09-14 from this sandbox.

### 1.1 `fja05680/sp500` (GitHub) — **recommended spine, 1996 → today**

- URL: https://github.com/fja05680/sp500 — **MIT licence**, 938 stars, last push
  2026-09-07 (actively maintained).
- Main file: `S&P 500 Historical Components & Changes (Updated).csv`, 5.5 MB, two columns
  `date, tickers` (comma-joined ticker list). **2,720 rows, 1996-01-02 (487 tickers) →
  2026-08-18 (503 tickers), 1,209 distinct tickers ever.** Each row is a snapshot on a
  date the membership changed.
- Companion: `sp500_ticker_start_end.csv` = one row per membership *span* (`ticker,
  start_date, end_date`), **1,262 spans** (some tickers have two spans, see the trap below).
- Provenance: the 1996–2019 core came from the dataset shipped with Andreas Clenow's
  *Trading Evolved* (Clenow's own source is not stated in the repo — it is almost certainly
  a commercial constituent feed, i.e. this is a second-hand copy of good data, not a
  reconstruction from Wikipedia). 2019 → present is maintained by hand from Wikipedia plus
  Google verification of each change date. Row density confirms this: 100–130 change rows
  per year through 2018, then 13–27 per year (only real changes, no re-snapshots).
- What's missing / caveats stated by the author: membership rarely equals exactly 500
  (mean 496 tickers/row); pre-2001 symbol data "may be incomplete"; tickers only — **no
  CUSIP, no CIK, no PERMNO**; no exit-reason column.
- **Trap (verified):** ticker reuse. `AAL` appears as a member 1996-01-02 → 1997-01-15
  (a different company) and again 2015-03-23 → 2024-09-23 (American Airlines). Any join on
  bare ticker without a date range will glue two companies together. §2 handles this.

### 1.2 Wikipedia, "Historical components of the S&P 500" — **live tail + exit reasons, 2007 → today**

- The change log is **no longer on** "List of S&P 500 companies"; an editor note there says
  changes are recorded in the separate article *Historical components of the S&P 500*.
  Fetch via `https://en.wikipedia.org/w/api.php?action=parse&page=Historical_components_of_the_S%26P_500&prop=wikitext&format=json`.
- Table columns: `Effective Date | Added (Ticker, Security) | Removed (Ticker, Security) |
  Reason | Refs`. **407 rows** on 2026-09-14.
- **Coverage by year (rows):** 1976: 2 · 1994–2006: 19 rows total · 2007: 11 · 2008: 8 ·
  2009: 13 · 2010: 11 · 2011: 19 · 2012: 18 · 2013: 19 · 2014: 16 · 2015–2026: 15–30 per
  year. S&P actually turns over roughly 20–30 names a year, so the table is **essentially
  absent before 2007, about half-complete 2007–2014, and near-complete from ~2015**. The
  robotwealth.com and riazarbi.github.io reconstructions independently reach the same
  conclusion (reliable "to about 2000/2012", degrading before).
- **The one thing only Wikipedia has: the free-text `Reason` column.** Keyword tally over
  the 407 rows: "acquir" 169 · "market cap" 144 · "spin" 96 · "merg" 19 · "bankrupt" 4.
  This is the raw material for classifying exits (§2), and it is the reason we keep
  Wikipedia in the pipeline at all rather than relying on fja05680 alone.
- Reliability: crowd-edited, dates are sometimes the announcement date and sometimes the
  effective date (the article's own editor note admits this). The "Refs" column links the
  S&P press release for most post-2015 rows — P1.4 can spot-check against those.

### 1.3 iShares IVV historical holdings — **independent cross-check, ~2006 → today**

- iShares' holdings download for IVV (the S&P 500 ETF) accepts an `asOfDate` parameter, so
  monthly holdings snapshots can be pulled back to roughly 2006–2007 (documented by
  riazarbi.github.io and teddykoker.com; **not re-verified from this sandbox** — iShares
  changes URL formats periodically).
- Use: not as a source of truth (the ETF holds cash, futures and occasional non-index
  positions, and tickers differ, e.g. `VISA` vs `V`), but as an **audit**: for a sample of
  month-ends, the fja05680 membership set and the IVV holdings set should overlap ~99%.
  Any month where they don't is a data bug to investigate.

### 1.4 Sources considered and rejected

| Source | Why not |
|---|---|
| Wikipedia page *revision history* (scrape old versions of the constituents table) | Reproduces the same 2012+ window as the changes table with more work; CIKs only from 2014. Dominated by fja05680. |
| Kaggle mirrors of "S&P 500 historical constituents" | Unlicensed copies of the same Clenow/Wikipedia data; no provenance advantage. |
| SEC EDGAR | Has no index-membership data. It *is* the authoritative free source for **why** a company stopped filing (Form 25 delisting, Form 15 deregistration, 8-K merger completion) — see §2.3 as an optional tiebreaker for exit classification. |
| S&P Dow Jones Indices press releases | The primary source, but no free bulk archive; Wikipedia's Refs column already links them. |
| Ken French Data Library | Already survivorship-free (built on CRSP) and already downloaded (P1.1) — but it is *portfolio* returns, not stock-level membership. It answers "does momentum work over 100 years" (P1.2), not "does *our* top-10 rule work on a real universe" (P1.4). Complementary, not a substitute. |

---

## 2. Price history for dead companies — the actual bottleneck

Membership is the easy half. The hard half is that a stock that left the index in 2011 by
being acquired has no Yahoo page in 2026. Live checks, 2026-09-14:

### 2.1 What free price sources actually carry (checked)

| Source | Delisted coverage | Free-tier limits | Verdict |
|---|---|---|---|
| **Yahoo / yfinance** (current `fetch_universe.py`) | **None.** Probed `YHOO`, `TWTR`, `CELG`: "No data found, symbol may be delisted". `TWX`, `BSC`: no chart at all. | n/a | Unusable for dead names. This is the root cause of our bias. |
| **Tiingo** (free "Starter" tier) | **Substantial.** Its public ticker manifest (`supported_tickers.zip`, no key needed) lists **16,478 US common stocks, of which 8,113 have an end date in the past** (i.e. dead), and 1,913 with history starting ≤1996. Acquired S&P names are there with correct spans: YHOO 1996→2017-06, TWX 1992→2018-06, AET 1977→2018-11, CELG 1990→2019-11, XLNX →2022-02, ATVI →2023-10, LNKD, ESRX, AGN, CTXS. **But bankruptcies are largely missing:** no LEH/LEHMQ, BSC, WCOM/WCOEQ, ENRN/ENRNQ, SIVB/SIVBQ, FRC/FRCB, GMGMQ, WAMUQ, KMRTQ. (AAMRQ — AMR's bankruptcy ticker — *is* there, 2001→2013.) | 50 req/hr, 1,000 req/day, **500 unique symbols/month**, 1 GB/mo. 30+ yrs of history. Internal-use-only licence (same footing as Yahoo: keep data gitignored). | **Recommended.** Only free source with real dead-name coverage. |
| **Alpha Vantage** (free key) | `LISTING_STATUS&state=delisted` returns every delisted US symbol with its delisting date — a free **delisting-date** oracle. Whether `TIME_SERIES_DAILY_ADJUSTED` still serves *prices* for a delisted symbol is **UNVERIFIED** (the demo key now returns `{}` for this endpoint; needs a free key, 25 requests/day). | 25 req/day | Secondary: use for delisting dates and, at 25/day, to patch a handful of names Tiingo lacks. |
| **Financial Modeling Prep** (free) | Has a "Delisted Companies" endpoint on the free plan; historical EOD price depth on the free plan is unclear and the docs page blocked the sandbox (HTTP 403). **UNVERIFIED.** | 250 req/day, 500 MB/30d | Tertiary patch source at best. |
| **Stooq** | Reported to carry some delisted symbols; blocked scripted access from the sandbox (returns HTML). **UNVERIFIED.** | bulk zip downloads | Manual fallback only. |

### 2.2 The coverage number that decides the window (checked)

I cross-matched all **1,262 S&P membership spans** (fja05680) against Tiingo's manifest,
requiring a Tiingo ticker whose own start/end dates cover the membership span:

| Backtest window starts | Spans in window | Fully priced by Tiingo | Ticker absent (dead) |
|---|---:|---:|---:|
| 1996-01 | 1,262 | 806 (64%) | 271 (269) |
| 2001-01 | 1,088 | 793 (73%) | 173 (171) |
| 2005-01 | 1,012 | 785 (78%) | 136 (134) |
| **2009-01** | **894** | **767 (86%)** | **77 (75)** |
| 2012-01 | 831 | 741 (89%) | 58 (56) |
| 2015-01 | 780 | 710 (91%) | 46 (44) |

Two readings of "absent":
- A chunk are **ticker renames, not missing companies** (visible in the absent list: ABC→COR,
  ANTM→ELV, BLL→BALL, BHGE→BKR, BK→BNY). Tiingo has them under the new symbol. A rename
  map (P1.4 builds it; start from the ~25-entry map in teddykoker's post and grow it from the
  Wikipedia `Reason` text) will recover a meaningful share of the 77.
- The rest are genuinely gone — and, per §2.1, they skew toward **bankruptcies and
  pre-2008 acquisitions**, i.e. the worst outcomes. Those are exactly the names whose
  absence inflates a backtest, so they cannot be silently dropped.

**Design decision: the primary no-hindsight run is 2009-01 → present** (~17.5 years, 86%+
priced before rename fixes, includes the 2009 momentum crash, 2011, 2015–16, 2018, 2020,
2022). A 1996 → present run is *possible* as a secondary, heavily-patched result — I do not
recommend spending P1.4 effort on it, because the 1927 → present survivorship-free answer to
"does momentum work over long history" is already coming from Ken French data (P1.2) at $0.

### 2.3 How each kind of exit is handled

Every membership span that ends is classified into one of four classes using the Wikipedia
`Reason` text (regex), with SEC EDGAR (Form 25 / Form 15 / 8-K "completion of acquisition")
as the tiebreaker when the reason is blank — most pre-2012 exits will be blank, so P1.4
should budget for a hand-classified table for those and commit it as a CSV with a source
column per row.

| Exit class | Frequency (Wikipedia tally) | Economic reality | How the panel treats it |
|---|---|---|---|
| **A. Acquired / merged / taken private** | ~170 of 407 rows | Holder receives cash or acquirer stock at roughly the last quoted price (the deal is already priced in by the final day). | Price series ends at last close. On the next rebalance the position is force-sold at that last close (turnover → cost charged, as it would be in reality). **No haircut.** If Tiingo lacks the series: try Alpha Vantage/FMP; if still missing, treat return during the held period as **0%** and flag it (`patched=missing_acq`). |
| **B. Bankruptcy / performance delisting** | ~4 of 407 rows (undercounted: pre-2012 reasons are blank; the 2008 financials are in this class) | Last CRSP-style quoted price overstates what a holder got. Shumway (1997, J. Finance) measured the missing delisting return at about **−30% for NYSE/AMEX**; Shumway & Warther (1999) about **−55% for Nasdaq**. | Append one synthetic final bar: `last_close × (1 − h)`, h = 0.30 NYSE / 0.55 Nasdaq, then the series ends. If the series is missing entirely from all free sources: **−100% from the last price we do have**, flagged (`patched=missing_bkr`). Conservative by design. |
| **C. Dropped for market-cap / representation reasons, still listed** | ~145 of 407 rows | Nothing happened to the holder; the stock just stops being *eligible*. | Price series continues normally (needed for momentum lookback if it re-enters). `eligible` flips to False from the effective date; a held position is sold at the next rebalance. |
| **D. Ticker change / spin-off / restructuring** | ~100 of 407 rows | No economic exit. | Rename map joins old and new symbol into one series. Spin-offs: parent keeps its adjusted series (Tiingo's adjClose already folds the distribution in); the spun-off child enters only if/when it is added to the index. |

**Why not a single simple rule ("last price then total loss for everything")?** Because
acquisitions outnumber bankruptcies ~40:1 in the S&P, and the average acquisition exits *at
a premium*. Treating them as −100% would swing the result from optimistic to absurdly
pessimistic and tell us nothing.

**Why not skip the haircut and just end the series at the last price?** Because that is the
CRSP delisting bias Shumway documented — a known, measured inflation — and it hits exactly
the class of exits (bankruptcies) that Tiingo is worst at. If we're going to patch, patch in
the direction the literature says.

**The skeptic's rail:** P1.4 runs the panel **twice** — an *optimistic* patch (class B
haircut 0, missing names 0%) and a *pessimistic* patch (haircuts as above, missing names
−100%) — and prints the momentum-vs-EW t-stat under both. **If the G1 verdict flips between
the two, the free data is not good enough to decide and we say so** rather than pick the one
we like. The output must also print how many spans were patched, by class.

---

## 3. What bias remains with the best free approach (honest list)

1. **Identifier risk (biggest).** We join on bare tickers with date ranges; CRSP uses
   PERMNOs precisely because tickers are reused (AAL) and renamed (ANTM→ELV). Every join
   error silently splices two companies. Mitigation: require Tiingo's own start/end dates to
   bracket the membership span; anything that fails is patched-and-flagged, never
   auto-joined. IVV-holdings overlap check (§1.3) catches whole-month errors.
2. **Missing-loser bias, residual.** ~14% of 2009+ spans are absent before rename fixes, and
   the absent ones skew toward bankruptcies. The haircut/−100% imputation is an *assumption*
   (Shumway's constants come from 1962–1995 data). The optimistic/pessimistic pair bounds it;
   it does not remove it.
3. **Membership-date fuzz.** Wikipedia mixes announcement and effective dates; fja05680's
   pre-2019 provenance is second-hand and unstated. S&P announces ~5 trading days before the
   effective date, so using the *effective* date as the eligibility flip is the *conservative*
   choice for lookahead (a stock becomes eligible slightly later than the market knew).
4. **The S&P 500 is not "the market".** It is committee-selected, requires positive trailing
   GAAP earnings for entry, and has a documented index-inclusion price effect. Using it as the
   universe imports a quality/profitability tilt and means our "eligible on date t" is
   "eligible *and already blessed by S&P*". This is point-in-time, so it is not lookahead —
   but it is a narrower claim than "momentum works on liquid US stocks".
5. **Momentum lookback uses pre-membership history.** A stock added in March 2015 needs
   prices back to March 2014 to have a 12-1 score. Tiingo has that history (its series start
   at IPO, not at index entry), so the *signal* is legitimate; only *selection* is masked by
   eligibility. P1.4 must not compute momentum only inside the membership window.
6. **Adjusted prices are computed today.** Tiingo's `adjClose` folds in all splits/dividends
   known as of now. For return arithmetic this is correct and standard; it is not lookahead.
   But dividend *timing* errors in a free feed are unaudited.
7. **Vendor survivorship inside Tiingo.** Its 8,113 dead-ticker count is large but its
   back-fill is visibly uneven before ~2008 (§2.2). The 2009+ window is chosen partly for
   this reason.
8. **Still one draw of history.** 2009–2026 is longer and more honest than 2019–2026 and
   includes a momentum crash, but it is still dominated by a secular bull. Only P1.2's
   century-long portfolio series addresses regime coverage.
9. **Exit-reason classification is regex + hand-labelling.** Errors between class A and
   class B change the haircut applied. The committed CSV with a source column per row makes
   every label auditable in P1.7.
10. **Licensing.** Tiingo and Yahoo data are internal-use-only; `research_data/` stays
    gitignored, exactly like `realdata/`. The *code* and the *membership table* (Wikipedia
    CC-BY-SA; fja05680 MIT) can be committed.

---

## 4. Fordham → WRDS / CRSP: partly resolved, needs a human to finish

**What I could verify (2026-09-14):**
- WRDS's public registration page lists its subscribing institutions in a dropdown.
  **"Fordham University" is in that list** (531 institutions; confirmed by fetching the raw
  page and grepping for the string, not by trusting a summary). So Fordham *is* a WRDS
  subscriber.
- A Fordham Gabelli graduate course bulletin (search-engine snippet of
  `bulletin.fordham.edu/courses/gfgb/`; the page itself blocked the sandbox) says students
  "engage in diverse projects using big data from proprietary financial databases, such as
  S&P Compustat, CRSP, Execucomp, ISS Directors, RepRisk, Thomson/Refinitiv". That is
  consistent with Fordham's WRDS bundle including **CRSP and Compustat**, which is the
  common configuration.
- Fordham Libraries' public A-Z database list does **not** list WRDS, CRSP or Compustat
  (only Value Line and a separate Bloomberg guide appear among finance vendors). Reading:
  WRDS at Fordham is probably administered through the Gabelli School / a WRDS
  representative rather than the library catalogue — which is normal, not a red flag.

**What I could not verify, and Tenzing needs to check directly:**
1. **Which datasets Fordham's WRDS licence includes.** WRDS subscriptions are per-dataset;
   "subscriber" does not guarantee CRSP daily stock files. The bulletin quote suggests yes.
2. **Which account classes Fordham grants.** WRDS's standard policy lets institutions choose:
   faculty and PhD only; master's on request; undergraduates often via a shared "class
   account" or a professor's sponsorship, and some schools disable student accounts in
   summer. Tenzing's status (undergrad / master's) determines this.
3. **How to check in ~10 minutes:** go to https://wrds-www.wharton.upenn.edu/register/,
   select Fordham University, enter an @fordham.edu address — the form shows the account
   types Fordham allows. Then/or email `library@fordham.edu` (Reference & Instruction) and
   ask "who is Fordham's WRDS representative, and does our subscription include CRSP daily
   stock and the CRSP/Compustat index-constituents files?"

**Even if the answer is yes, two limits (state them now so nobody is surprised):**
- **Licence scope.** Academic WRDS/CRSP terms are for academic research. Building a
  strategy that trades real money on data pulled under a student licence is at minimum a
  grey area; re-distributing the data (committing it, serving it from `api_server.py`) is a
  clear violation. Proposed use: **validation only** — run the identical P1.4 pipeline on
  CRSP membership + CRSP prices (with real delisting returns, `dlret`) and compare the
  momentum-vs-EW t-stat against the free-data run. If they agree, we trust the free
  pipeline going forward. If they disagree, we learn exactly where the free data lies.
  CRSP never becomes the production universe.
- **Access lifetime.** Student accounts end at graduation. A pipeline that depends on CRSP
  dies with the login; the free pipeline is the one that has to be right.

---

## 5. Paid sources — PROPOSAL, NOT APPROVED

Cost policy: paid only if ~20× more helpful than the free path *and* signed off by Tenzing
first. My assessment: **nothing here clears 20× for Phase 1.** Listed for completeness and
so the numbers are on file.

| Option | Cost (checked 2026-09-14) | What it adds over the free plan | 20× test |
|---|---|---|---|
| **Tiingo Power** | $30/mo (or $300/yr); 109k symbols/mo, 10k req/hr | Pull all ~900–1,260 tickers in one afternoon instead of staging 500 symbols/month over 2–3 months on the free tier. Same data. | **No.** It buys *time*, not *truth*. A one-month subscription cancelled after the pull is a defensible $30 convenience — but it is Tenzing's call, and the default plan (§6) works without it. |
| **Sharadar (SEP + S&P 500 constituents)**, personal licence | $69/mo or $499/yr "Full History" (1998+); $29/mo for 5-yr history | Curated survivorship-free prices, **explicit delist reasons and dates, ticker-change table, and its own S&P 500 point-in-time constituents table** — i.e. it replaces §1 and §2 entirely with one maintained feed. | **Not for P1.4.** For the 2009+ window our free coverage is 86%+ before rename fixes; Sharadar takes that to ~100% and removes the identifier risk. That is a real improvement, maybe 2–3×, not 20×. **Revisit if G1 passes:** Phase 2 needs a *maintained* constituent feed every month, and hand-maintaining Wikipedia joins forever is where a $499/yr feed starts to look 20× better than a person. |
| **Norgate Data, Platinum US** | $630/yr | Same as Sharadar plus deeper pre-2000 delisted coverage; desktop-app delivery (Windows-centric, Python via NDU). | No. Same argument, higher price, worse fit for a pandas pipeline. |
| **EODHD "EOD Historical Data"** | €19.99/mo | 26k+ US tickers incl. delisted from ~2000; `delisted=1` exchange listing. | No. Overlaps Tiingo-free; no constituent history in this tier. |
| **CRSP via WRDS** | $0 *if* Fordham grants access (§4) | The gold standard: PERMNO identifiers, actual delisting returns, index membership. | Not a purchase decision. Validation use only, per §4. |

**Recommendation:** build P1.4 on the free plan. If Tenzing wants to spend $30 once to skip
two months of staged Tiingo pulls, that is a reasonable exception to raise, not something
this document approves. Put Sharadar on the Phase-2 decision list, gated on G1.

---

## 6. The plan P1.4 should implement (spec, no code)

**Files (all new; `xsect.py` gets one new optional input):**

1. `fetch_membership.py` (run locally) → `research_data/universe/membership.csv`
   - Columns: `ticker, start_date, end_date, exit_class {A,B,C,D,active}, exit_reason_text,
     source {fja05680|wikipedia|hand}, new_ticker (for class D)`.
   - Spine: `sp500_ticker_start_end.csv` from fja05680 (pull at a pinned commit hash; record
     it). Tail: parse the Wikipedia table for rows after fja's last date and for the
     `Reason` text of every row it has. Rename map: `research_data/universe/renames.csv`,
     hand-curated, committed (it is small and it is *ours*).
   - **This CSV is committable** (MIT + CC-BY-SA). Commit it with the commit hash and fetch
     date in a header comment so P1.7 can reproduce it.
2. `fetch_pit_prices.py` (run locally, Tiingo free key in `.env`) → `research_data/pit_prices/<ticker>.csv`
   - Same schema as `realdata/*.csv` so `data.load_csv` works unchanged.
   - Pulls the *full* Tiingo history per ticker (not just the membership window — §3.5).
   - Staging: ≤500 new symbols per calendar month; keeps `manifest.json` of what's pulled, so
     it is idempotent and resumable. Order: 2009+ members first, then 1996–2008.
   - Writes `coverage.json`: per span, `priced_full | priced_partial | missing`, so the
     backtest can print the patch counts.
3. `pit_panel.py` → builds the (dates × tickers) close panel **and** the `eligible` mask from
   the two above, applying §2.3 (haircut bar for class B, series end for A, mask flip for C,
   join for D). Parameterised `patch='optimistic'|'pessimistic'`.
4. `xsect.py`: `target_weights(..., eligible=None)` and `_ew_weights(..., eligible=None)`.
   When given, a name is selectable at month-end `t` only if `eligible.loc[t, name]`.
   Everything else — `shift(1)`, costs, `significance_vs_ew` — unchanged. The no-lookahead
   invariant stays in the engine.

**Acceptance tests (P1.4 must run and show output):**
- *Lookahead guard:* for every span, the ticker is never held on a date before `start_date`
  and never *selected* on a rebalance date on/after `end_date`. Assert over the whole
  weights frame.
- *Panel sanity vs an external free benchmark:* the EW-of-eligible-universe leg, rebalanced
  monthly at 3/1 bps, should track **RSP** (Invesco S&P 500 Equal Weight ETF, live since
  2003, fetchable from Yahoo) to within a few percent a year over 2009–2026. If our EW leg
  and RSP diverge materially, the membership or price data is wrong — this is the single
  most powerful free check available and it costs nothing.
- *Patch report:* printed table of spans by exit class × price status (full/partial/missing),
  and the momentum-vs-EW t-stat under both `optimistic` and `pessimistic`.
- *Reproduction of the old result:* running the new code with `eligible=None` on
  `realdata/` must reproduce the 2026-09-13 numbers (t ≈ 0.34) exactly.
- *Old-vs-new headline:* momentum and EW total return on the 30-name 2019–2026 universe vs
  the point-in-time universe over the same 2019–2026 dates, side by side. The gap between
  those two EW rows *is* the measured survivorship + winner-selection bias, and it should be
  quoted in the Thesis 001 writeup regardless of how the momentum verdict lands.

**G1 criterion 2 as it should now read:** "top-10 beats EW of the point-in-time S&P 500
universe, 2009-01 → present, with t ≥ 2 under the *pessimistic* patch, and the verdict does
not flip under the optimistic one."

---

## 7. Summary for the standup

- **Membership (free):** fja05680/sp500 (MIT, 1996→, 1,262 spans, actively maintained) as
  the spine; Wikipedia's *Historical components* table for the live tail and the exit-reason
  text; IVV holdings as an audit.
- **Prices (free):** Tiingo Starter — the only free feed with real dead-name coverage
  (8,113 delisted US stocks). 86% of 2009+ membership spans fully priced before rename
  fixes; bankruptcies are its blind spot and get a literature-based haircut, bounded by an
  optimistic/pessimistic pair.
- **Window:** 2009 → present as the primary no-hindsight run. Long history is P1.2's job
  (Ken French, 1927→, already survivorship-free).
- **Bias that remains:** ticker-identifier joins, residual missing losers, membership-date
  fuzz, S&P's own selection rules, one bull-dominated draw. All listed in §3, none hidden.
- **Fordham/WRDS:** Fordham **is** a WRDS subscriber (verified). Whether CRSP is in the
  bundle and whether Tenzing's account class can log in **needs Tenzing to check** (§4,
  ten-minute procedure). Use would be validation-only under an academic licence.
- **Paid:** nothing clears 20× for Phase 1. Tiingo Power ($30, one month) is a
  time-saver to raise with Tenzing, not an approval. Sharadar ($499/yr) goes on the Phase-2
  list, gated on G1. **PROPOSAL, NOT APPROVED.**

*Sources checked live 2026-09-14: github.com/fja05680/sp500 (API + raw CSVs);
en.wikipedia.org "Historical components of the S&P 500" (wikitext via API);
apimedia.tiingo.com supported_tickers.zip; tiingo.com/about/pricing;
query1.finance.yahoo.com chart API; wrds-www.wharton.upenn.edu/register/;
fordham.libguides.com/az.php; sharadar.com/subscribe (via search snippet);
norgatedata.com; eodhd.com/pricing; Shumway (1997) J. Finance 52:327–340; Shumway & Warther
(1999) J. Finance 54:2361–2379; robotwealth.com and riazarbi.github.io S&P reconstruction
posts; teddykoker.com IVV-holdings post.*
