"""Point-in-time S&P 500 membership (P1.4, design: research/audits/2026-09-survivorship-design.md §6.1).

Run LOCALLY (needs internet). Writes TWO committable CSVs:

    research_data/universe/membership.csv   one row per membership SPAN
    research_data/universe/renames.csv      old_ticker -> new_ticker (class D joins)

Why: `fetch_universe.py` hard-codes 30 tickers picked in 2026, so every name in it
survived to 2026 *and* was picked because it won 2019-2026. This file rebuilds "who was
actually in the index on date t", including the names that later died.

Sources (both free, both redistributable, which is why the output is committable):
  * SPINE -- fja05680/sp500 `sp500_ticker_start_end.csv` (MIT), pulled at a PINNED commit
    so P1.7 can reproduce this exact table. One row per membership span since 1996.
  * TAIL + EXIT REASONS -- Wikipedia "Historical components of the S&P 500" (CC-BY-SA),
    via the MediaWiki parse API. Its free-text `Reason` column is the only free source
    for WHY a name left, which is what the exit classes below need.

Exit classes (design doc §2.3 -- pit_panel.py applies them):
    A  acquired / merged / taken private   -> series ends at last close, no haircut
    B  bankruptcy / performance delisting  -> Shumway haircut on a synthetic final bar
    C  dropped (market cap / rep), still listed -> series continues, eligibility flips off
    D  ticker change / spin-off            -> rename map joins the two series
    active                                 -> still in the index

Caveats, stated up front (design doc §1.2, §3):
  * Wikipedia's change log is essentially absent before 2007, ~half complete 2007-2014,
    near complete from ~2015. Spans that end with no Wikipedia row default to class C,
    which is the right *majority* guess and the wrong one for pre-2008 bankruptcies.
    Every row carries a `source` column so P1.7 can audit exactly which label came from
    text and which came from the default.
  * Ticker reuse is real (AAL is two different companies). This file keeps spans separate;
    it is pit_panel.py that refuses to join a price series that does not bracket the span.

    python3 fetch_membership.py
"""
import csv
import collections
import datetime
import io
import json
import os
import re
import urllib.request

# Pinned so the table is reproducible. Bump deliberately, never silently.
FJA_COMMIT = 'a2430f2af0c79ddf0748e91de11bdeb1616ab5a7'   # fja05680/sp500, 2026-09-07
FJA_URL = ('https://raw.githubusercontent.com/fja05680/sp500/'
           f'{FJA_COMMIT}/sp500_ticker_start_end.csv')
WIKI_URL = ('https://en.wikipedia.org/w/api.php?action=parse'
            '&page=Historical_components_of_the_S%26P_500&prop=wikitext&format=json')
UA = 'algo-trading-research/1.0 (backtest harness; membership reconstruction)'

OUT_DIR = 'research_data/universe'
MEMBERSHIP_CSV = os.path.join(OUT_DIR, 'membership.csv')
RENAMES_CSV = os.path.join(OUT_DIR, 'renames.csv')

# Match a span's end_date to a Wikipedia row within this many days. Wikipedia mixes
# announcement and effective dates (its own editor note says so), and fja's snapshot date
# is the last date the ticker appears in the list -- a few days of slack is required.
MATCH_TOL_DAYS = 30

# The auto rename-detector (see detect_renames) is only trustworthy where the Wikipedia
# change log is near complete. Before this date it produces false positives that would
# splice two different companies together -- the exact failure mode design doc §3.1 warns
# about -- so earlier renames must come from the hand-seeded map below.
AUTO_RENAME_FROM = datetime.date(2015, 1, 1)

# Hand-curated seed (design doc §2.2 names the first five). NOT exhaustive -- it covers the
# renames we could verify; anything missed shows up in coverage.json as a `missing` span
# rather than as a silent bad join.
HAND_RENAMES = [
    # old,   new,    effective,     note
    ('ABC',  'COR',  '2023-08-30', 'AmerisourceBergen -> Cencora'),
    ('ANTM', 'ELV',  '2022-06-28', 'Anthem -> Elevance Health'),
    ('BLL',  'BALL', '2022-05-10', 'Ball Corporation ticker change'),
    ('BHGE', 'BKR',  '2019-10-18', 'Baker Hughes a GE company -> Baker Hughes'),
    ('BK',   'BNY',  '2026-05-21', 'Bank of New York Mellon -> BNY'),
    ('FB',   'META', '2022-06-09', 'Facebook -> Meta Platforms'),
    ('HRS',  'LHX',  '2019-06-01', 'Harris -> L3Harris Technologies'),
    ('TMK',  'GL',   '2019-08-08', 'Torchmark -> Globe Life'),
    ('JEC',  'J',    '2019-12-10', 'Jacobs Engineering -> Jacobs Solutions'),
    ('CTL',  'LUMN', '2020-09-18', 'CenturyLink -> Lumen Technologies'),
    ('MYL',  'VTRS', '2020-11-17', 'Mylan -> Viatris (Upjohn combination)'),
    ('LB',   'BBWI', '2021-08-03', 'L Brands -> Bath & Body Works'),
    ('COG',  'CTRA', '2021-10-04', 'Cabot Oil & Gas -> Coterra Energy'),
    ('VIAC', 'PARA', '2022-02-17', 'ViacomCBS -> Paramount Global'),
    ('NLOK', 'GEN',  '2022-11-08', 'NortonLifeLock -> Gen Digital'),
    ('PKI',  'RVTY', '2023-05-16', 'PerkinElmer -> Revvity'),
    ('RE',   'EG',   '2023-07-10', 'Everest Re -> Everest Group'),
    ('FISV', 'FI',   '2023-06-07', 'Fiserv ticker change'),
    ('PEAK', 'DOC',  '2024-03-04', 'Healthpeak Properties ticker change'),
    ('WRK',  'SW',   '2024-07-08', 'WestRock -> Smurfit WestRock'),
    ('BRK.B', 'BRK-B', '1996-01-02', 'punctuation only -- Tiingo spells class shares with a dash'),
    ('BF.B', 'BF-B', '1996-01-02', 'punctuation only -- Tiingo spells class shares with a dash'),
    # Found by checking which "absent from Tiingo" 2009+ spans are really live companies
    # under a newer symbol (Tiingo carries the CURRENT symbol with the full back history).
    # The effective_date below is the span end fja records; where the ticker change happened
    # after the index exit the note says so -- the join is still the right one for prices.
    ('SYMC', 'NLOK', '2019-11-05', 'Symantec -> NortonLifeLock (then NLOK -> GEN)'),
    ('UTX',  'RTX',  '2020-04-03', 'United Technologies -> Raytheon Technologies'),
    ('CBS',  'VIAC', '2019-12-05', 'CBS/Viacom re-merger -> ViacomCBS (then VIAC -> PARA)'),
    ('WLTW', 'WTW',  '2022-01-10', 'Willis Towers Watson ticker change'),
    ('FLT',  'CPAY', '2024-03-25', 'FLEETCOR -> Corpay'),
    ('CDAY', 'DAY',  '2024-02-01', 'Ceridian -> Dayforce'),
    ('DWDP', 'DD',   '2019-06-03', 'DowDuPont -> DuPont de Nemours'),
    ('FBHS', 'FBIN', '2022-12-19', 'Fortune Brands Home & Security -> Fortune Brands Innovations'),
    ('GPS',  'GAP',  '2022-02-02', 'Gap Inc; ticker GPS -> GAP in 2024, after the index exit'),
    ('HFC',  'DINO', '2021-06-04', 'HollyFrontier -> HF Sinclair (2022, after the index exit)'),
    ('FII',  'FHI',  '2013-01-02', 'Federated Investors -> Federated Hermes (2021)'),
    ('KORS', 'CPRI', '2018-09-19', 'Michael Kors -> Capri Holdings'),
    ('ADS',  'BFH',  '2020-06-22', 'Alliance Data Systems -> Bread Financial (2022)'),
    ('WYND', 'TNL',  '2018-05-31', 'Wyndham Destinations -> Travel + Leisure (2021)'),
    # NOT added on purpose: ESV -> VAL (Ensco/Valaris). Tiingo's VAL is two different
    # companies (Valspar 1992-2017, then Valaris) -- the ticker-reuse trap of design doc
    # §1.1. A wrong join here would silently splice two firms, so ESV stays unpriced.
]

# Exit-class overrides for spans Wikipedia does not cover (design doc §2.3 asks for exactly
# this: a hand-classified, committed table with a source column). Only class B matters
# numerically -- A vs C is economically inert whenever the price series exists, because both
# just end/continue the series and flip eligibility. So this list stays deliberately short:
# verified bankruptcy/receivership exits the regex could not see.
HAND_EXITS = [
    # ticker, end_date,     class, reason text
    ('MTLQQ', '2009-06-03', 'B', 'General Motors filed Chapter 11 on 2009-06-01 and was '
                                 'removed from the index; equity became Motors Liquidation.'),
]


# ---------------------------------------------------------------------------- fetching

def _get(url, timeout=120):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_spans():
    """fja05680 membership spans -> [{ticker, start_date, end_date-or-''}]."""
    txt = _get(FJA_URL).decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(txt)))
    return [{'ticker': r['ticker'].strip(),
             'start_date': r['start_date'].strip(),
             'end_date': (r.get('end_date') or '').strip()} for r in rows]


def _strip_wiki(s):
    s = re.sub(r'<ref[^>]*/>', '', s)
    s = re.sub(r'<ref.*?</ref>', '', s, flags=re.S)
    s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)
    return s.replace("'''", '').replace("''", '').strip()


def _parse_date(s):
    s = s.strip().replace('\xa0', ' ')
    for fmt in ('%B %d, %Y', '%b %d, %Y', '%B %d %Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def fetch_wiki_changes():
    """Wikipedia's change table -> [{date, added, added_name, removed, removed_name, reason}].

    Wikitext rows are `|-`-separated; cells arrive either one-per-line (`|X`) or
    pipe-joined (`|| X || Y`), so both spellings are handled."""
    payload = json.loads(_get(WIKI_URL).decode('utf-8'))
    wt = payload['parse']['wikitext']['*']
    start = wt.find('{| class="wikitable sortable" id="changes"')
    if start < 0:
        raise RuntimeError('Wikipedia changes table not found -- the article layout changed.')
    table = wt[start:wt.find('\n|}', start)]
    out = []
    for raw in table.split('\n|-')[1:]:
        cells = []
        for line in _strip_wiki(raw).split('\n'):
            line = line.strip()
            if not line:
                continue
            if not line.startswith('|'):           # wrapped continuation of the last cell
                if cells:
                    cells[-1] = (cells[-1] + ' ' + line).strip()
                continue
            for part in line.lstrip('|').split('||'):
                cells.append(part.strip())
        if len(cells) < 6:
            continue
        d = _parse_date(cells[0])
        if d is None:
            continue
        out.append({'date': d, 'added': cells[1], 'added_name': cells[2],
                    'removed': cells[3], 'removed_name': cells[4], 'reason': cells[5]})
    return out


# ------------------------------------------------------------------- classification

_RE_BANKRUPT = re.compile(r'bankrupt|chapter 11|chapter 7|receivership|liquidat|'
                          r'insolven|seized by|placed into administration', re.I)
_RE_RENAME = re.compile(r'ticker (change|symbol)|symbol change|renamed|name change|'
                        r'changed its name|spin[- ]?off|spun off|spinoff|reverse morris',
                        re.I)
_RE_ACQUIRE = re.compile(r'acquir|merg|bought by|taken private|take[ns] private|'
                         r'purchased by|buyout|tender offer|combined with|'
                         r'completed its acquisition', re.I)


def classify_reason(reason):
    """Wikipedia `Reason` free text -> exit class. Order is deliberate: bankruptcy is the
    rarest and most specific, rename/spin-off next, acquisition next, and the default is
    C (dropped for market-cap / representation reasons), which is what ~145 of the 407
    Wikipedia rows actually say (design doc §2.3)."""
    if not reason:
        return 'C'                       # no text at all -> the majority outcome
    if _RE_BANKRUPT.search(reason):
        return 'B'
    if _RE_RENAME.search(reason):
        return 'D'
    if _RE_ACQUIRE.search(reason):
        return 'A'
    return 'C'


# ------------------------------------------------------------------------- renames

def detect_renames(spans, wiki):
    """Find ticker renames that fja05680 records as `ticker X span ends / ticker Y span
    starts, same date` and Wikipedia does NOT record at all.

    The article's own editor note says ticker changes are deliberately excluded from the
    change table, so "one span ends + one span starts on date D, and Wikipedia has no
    add/remove row anywhere near D" is a strong rename signature -- but ONLY in the window
    where the Wikipedia log is near complete. Before AUTO_RENAME_FROM the log is half
    missing, so the same pattern also fires on ordinary replacements (e.g. 2009-01-06
    UST/IRM, where UST was acquired by Altria). Those get skipped."""
    ends, starts = collections.defaultdict(list), collections.defaultdict(list)
    for s in spans:
        if s['end_date']:
            ends[s['end_date']].append(s['ticker'])
        starts[s['start_date']].append(s['ticker'])
    wiki_removed, wiki_added = collections.defaultdict(list), collections.defaultdict(list)
    for r in wiki:
        if r['removed']:
            wiki_removed[r['removed']].append(r['date'])
        if r['added']:
            wiki_added[r['added']].append(r['date'])

    def near(dates, d):
        return any(abs((x - d).days) <= MATCH_TOL_DAYS for x in dates)

    found = []
    for ds, enders in ends.items():
        d = datetime.date.fromisoformat(ds)
        if d < AUTO_RENAME_FROM:
            continue
        beginners = starts.get(ds, [])
        if len(enders) != 1 or len(beginners) != 1:
            continue
        old, new = enders[0], beginners[0]
        if near(wiki_removed.get(old, []), d) or near(wiki_added.get(new, []), d):
            continue                      # a real index change, not a rename
        found.append((old, new, ds, 'auto', 'same-day span handoff, no Wikipedia row'))
    return sorted(found, key=lambda r: r[2])


def build_rename_map(spans, wiki):
    """Hand seed + auto-detected, de-duplicated on (old, effective_date)."""
    rows = [(o, n, d, 'hand', note) for o, n, d, note in HAND_RENAMES]
    have = {(r[0], r[2]) for r in rows}
    for r in detect_renames(spans, wiki):
        if (r[0], r[2]) not in have:
            rows.append(r)
            have.add((r[0], r[2]))
    return sorted(rows, key=lambda r: (r[2], r[0]))


def resolve_rename(ticker, chain, _seen=None):
    """Follow a rename chain to the symbol the data vendor uses today.
    FISV -> FI -> FISV exists in this data, so the visited-set is not paranoia."""
    seen = _seen or set()
    cur = ticker
    while cur in chain and cur not in seen:
        seen.add(cur)
        nxt = chain[cur]
        if nxt in seen:
            break
        cur = nxt
    return cur


# ---------------------------------------------------------------------------- build

def build_membership(spans, wiki, rename_rows):
    """Attach an exit class, the reason text, and a source to every span."""
    removed = collections.defaultdict(list)
    for r in wiki:
        if r['removed']:
            removed[r['removed']].append(r)
    rename_by_old = {}
    for old, new, eff, src, note in rename_rows:
        rename_by_old.setdefault(old, []).append((eff, new))
    hand_exits = {(t, d): (c, why) for t, d, c, why in HAND_EXITS}

    out = []
    for s in spans:
        tk, sd, ed = s['ticker'], s['start_date'], s['end_date']
        if not ed:
            out.append({'ticker': tk, 'start_date': sd, 'end_date': '',
                        'exit_class': 'active', 'exit_reason_text': '',
                        'source': 'fja05680', 'new_ticker': ''})
            continue
        d = datetime.date.fromisoformat(ed)
        # 0. A hand-verified exit class beats everything (it exists because the text is absent).
        if (tk, ed) in hand_exits:
            cls, why = hand_exits[(tk, ed)]
            out.append({'ticker': tk, 'start_date': sd, 'end_date': ed, 'exit_class': cls,
                        'exit_reason_text': why, 'source': 'hand', 'new_ticker': ''})
            continue
        # 1. A rename dated at this span's end wins: it is not an economic exit at all.
        new_ticker = ''
        for eff, new in rename_by_old.get(tk, []):
            if abs((datetime.date.fromisoformat(eff) - d).days) <= MATCH_TOL_DAYS:
                new_ticker = new
                break
        if new_ticker:
            out.append({'ticker': tk, 'start_date': sd, 'end_date': ed,
                        'exit_class': 'D', 'exit_reason_text': f'ticker change -> {new_ticker}',
                        'source': 'hand', 'new_ticker': new_ticker})
            continue
        # 2. Otherwise the nearest Wikipedia removal row for this ticker, if any.
        cands = [r for r in removed.get(tk, []) if abs((r['date'] - d).days) <= MATCH_TOL_DAYS]
        if cands:
            best = min(cands, key=lambda r: abs((r['date'] - d).days))
            reason = best['reason']
            out.append({'ticker': tk, 'start_date': sd, 'end_date': ed,
                        'exit_class': classify_reason(reason),
                        'exit_reason_text': reason, 'source': 'wikipedia', 'new_ticker': ''})
        else:
            # 3. No text anywhere -> the default. Honest, and flagged by `source`.
            out.append({'ticker': tk, 'start_date': sd, 'end_date': ed,
                        'exit_class': 'C', 'exit_reason_text': '',
                        'source': 'fja05680', 'new_ticker': ''})
    return sorted(out, key=lambda r: (r['start_date'], r['ticker']))


def apply_wiki_tail(membership, wiki, spans):
    """Wikipedia rows AFTER fja's last snapshot date: open spans for additions, close
    spans for removals. Usually empty (fja is updated weekly); here so a stale pin does
    not silently lose the last few weeks of index changes."""
    last = max(s['end_date'] for s in spans if s['end_date'])
    last_d = datetime.date.fromisoformat(last)
    tail = [r for r in wiki if r['date'] > last_d]
    if not tail:
        return membership, 0
    by_ticker = {}
    for m in membership:
        if m['exit_class'] == 'active':
            by_ticker[m['ticker']] = m
    n = 0
    for r in sorted(tail, key=lambda r: r['date']):
        if r['removed'] and r['removed'] in by_ticker:
            m = by_ticker.pop(r['removed'])
            m['end_date'] = r['date'].isoformat()
            m['exit_class'] = classify_reason(r['reason'])
            m['exit_reason_text'] = r['reason']
            m['source'] = 'wikipedia'
            n += 1
        if r['added'] and r['added'] not in by_ticker:
            m = {'ticker': r['added'], 'start_date': r['date'].isoformat(), 'end_date': '',
                 'exit_class': 'active', 'exit_reason_text': '', 'source': 'wikipedia',
                 'new_ticker': ''}
            membership.append(m)
            by_ticker[r['added']] = m
            n += 1
    return sorted(membership, key=lambda r: (r['start_date'], r['ticker'])), n


# ----------------------------------------------------------------------------- io

def write_membership(rows, fetched_on, n_wiki, n_tail):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(MEMBERSHIP_CSV, 'w', newline='') as f:
        f.write('# Point-in-time S&P 500 membership spans (P1.4).\n')
        f.write(f'# Built by fetch_membership.py on {fetched_on}.\n')
        f.write(f'# Spine: github.com/fja05680/sp500 sp500_ticker_start_end.csv @ {FJA_COMMIT} (MIT).\n')
        f.write(f'# Exit reasons: en.wikipedia.org "Historical components of the S&P 500" '
                f'({n_wiki} change rows, CC-BY-SA); {n_tail} row(s) applied as a post-spine tail.\n')
        f.write('# exit_class: A acquired/merged | B bankruptcy/performance delisting | '
                'C dropped, still listed | D ticker change/spin-off | active.\n')
        f.write('# source=fja05680 means NO exit text was available and class C is the DEFAULT, '
                'not a finding (Wikipedia is ~absent before 2007).\n')
        w = csv.DictWriter(f, fieldnames=['ticker', 'start_date', 'end_date', 'exit_class',
                                          'exit_reason_text', 'source', 'new_ticker'])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_renames(rows, fetched_on):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(RENAMES_CSV, 'w', newline='') as f:
        f.write('# Ticker renames / spin-off symbol changes (class D joins). NOT EXHAUSTIVE.\n')
        f.write(f'# Built by fetch_membership.py on {fetched_on}. source=hand is verified by a\n')
        f.write('# human; source=auto is "one span ends + one starts the same day with no\n')
        f.write(f'# Wikipedia row", trusted only from {AUTO_RENAME_FROM} on (see detect_renames).\n')
        w = csv.writer(f)
        w.writerow(['old_ticker', 'new_ticker', 'effective_date', 'source', 'note'])
        for r in rows:
            w.writerow(r)


def load_membership(path=MEMBERSHIP_CSV):
    """Read membership.csv back (skipping the `#` header block)."""
    with open(path) as f:
        lines = [l for l in f if not l.startswith('#')]
    return list(csv.DictReader(io.StringIO(''.join(lines))))


def load_renames(path=RENAMES_CSV):
    """-> {old_ticker: new_ticker} (last rename wins for a chain start)."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        lines = [l for l in f if not l.startswith('#')]
    out = {}
    for r in csv.DictReader(io.StringIO(''.join(lines))):
        out[r['old_ticker']] = r['new_ticker']
    return out


def main():
    today = datetime.date.today().isoformat()
    print('Fetching fja05680/sp500 membership spans '
          f'(pinned commit {FJA_COMMIT[:10]}) ...')
    spans = fetch_spans()
    print(f'  {len(spans)} spans, {len({s["ticker"] for s in spans})} distinct tickers, '
          f'{sum(1 for s in spans if not s["end_date"])} currently active.')

    print('Fetching Wikipedia "Historical components of the S&P 500" ...')
    wiki = fetch_wiki_changes()
    print(f'  {len(wiki)} change rows, {wiki[-1]["date"]} -> {wiki[0]["date"]}.')

    renames = build_rename_map(spans, wiki)
    n_hand = sum(1 for r in renames if r[3] == 'hand')
    print(f'  rename map: {len(renames)} entries ({n_hand} hand-verified, '
          f'{len(renames) - n_hand} auto-detected from {AUTO_RENAME_FROM}).')

    membership = build_membership(spans, wiki, renames)
    membership, n_tail = apply_wiki_tail(membership, wiki, spans)

    counts = collections.Counter(m['exit_class'] for m in membership)
    srcs = collections.Counter(m['source'] for m in membership)
    print('\nExit classes: ' + '  '.join(f'{k}={counts[k]}' for k in ('A', 'B', 'C', 'D', 'active')))
    print('Label source: ' + '  '.join(f'{k}={v}' for k, v in sorted(srcs.items())))
    ended = [m for m in membership if m['exit_class'] != 'active']
    labelled = sum(1 for m in ended if m['source'] == 'wikipedia')
    print(f'  {labelled}/{len(ended)} ended spans carry real Wikipedia exit text; the rest '
          f'default to C.')

    write_membership(membership, today, len(wiki), n_tail)
    write_renames(renames, today)
    print(f'\nWrote {MEMBERSHIP_CSV} ({len(membership)} spans)')
    print(f'Wrote {RENAMES_CSV} ({len(renames)} renames)')


if __name__ == '__main__':
    main()
