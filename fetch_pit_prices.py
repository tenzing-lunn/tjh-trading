"""Point-in-time price history from Tiingo (P1.4, design doc §6.2). Run LOCALLY.

Yahoo/yfinance has NO data for delisted names (design doc §2.1: YHOO, TWTR, CELG, TWX, BSC
all return "symbol may be delisted"), which is the root cause of the survivorship bias in
`realdata/`. Tiingo's free tier is the only free feed that carries dead tickers, so this
module is the bridge between `membership.csv` (who was in the index, when) and prices for
those names -- including the ones that no longer exist.

    research_data/pit_prices/<SYMBOL>.csv   same schema as realdata/*.csv (data.load_csv works)
    research_data/pit_prices/manifest.json  per-symbol fetch status, for resuming
    research_data/pit_prices/coverage.json  per membership SPAN: priced_full/partial/missing

THE FREE TIER IS THE DESIGN CONSTRAINT, NOT AN ACCIDENT.
Tiingo Starter allows **500 unique new symbols per calendar month** (plus 50 req/hr,
1000 req/day, 1 GB/mo). The 2009+ window needs ~800 symbols, so a full pull takes two or
three monthly runs. This script is therefore *staged and resumable*: it records what it has
already pulled, refuses to start more than MAX_NEW_SYMBOLS_PER_MONTH new symbols in a
calendar month, and stops cleanly (writing the manifest) the moment Tiingo rate-limits it.
Re-run it next month and it picks up exactly where it stopped. It never silently
half-completes.

Fetch order (design doc §6.2): symbols whose membership overlaps 2009-01 first -- and inside
that era, the names with the most eligible months first, so a partial pull is still a usable
panel -- then the 1996-2008-only names.

    python3 fetch_pit_prices.py                 # resume; up to the monthly cap
    python3 fetch_pit_prices.py --max-new 50    # small run
    python3 fetch_pit_prices.py --plan          # print the queue, fetch nothing
    python3 fetch_pit_prices.py --coverage      # rebuild coverage.json from what's on disk
"""
import argparse
import csv
import collections
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd

from fetch_membership import (load_membership, load_renames, MEMBERSHIP_CSV)

OUT_DIR = 'research_data/pit_prices'
MANIFEST = os.path.join(OUT_DIR, 'manifest.json')
COVERAGE = os.path.join(OUT_DIR, 'coverage.json')
TICKER_META = os.path.join(OUT_DIR, '_tiingo_supported_tickers.csv')

TIINGO_TICKERS_URL = 'https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip'
TIINGO_PRICES = 'https://api.tiingo.com/tiingo/daily/{sym}/prices'
HISTORY_START = '1990-01-01'          # full history, NOT the membership window (design §3.5)
UA = 'algo-trading-research/1.0'

MAX_NEW_SYMBOLS_PER_MONTH = 500       # Tiingo free tier, hard cap
REQ_SLEEP = 0.35                      # be a polite guest on a free tier
ERA_START = datetime.date(2009, 1, 1)  # the primary no-hindsight window (design §2.2)
TODAY = datetime.date.today()

# Benchmarks we need from the same vendor: SPY (opportunity cost) and RSP (Invesco S&P 500
# Equal Weight -- the external check that our EW-of-eligible leg is not fantasy).
BENCHMARKS = ['SPY', 'RSP']


# ------------------------------------------------------------------ env / http

def load_dotenv(path='.env'):
    """Same stdlib pattern engine_api.py uses -- no python-dotenv dependency, and real
    environment variables always win."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())


def api_key():
    load_dotenv()
    k = os.environ.get('TIINGO_API_KEY', '').strip()
    if not k:
        sys.exit('TIINGO_API_KEY not set (put it in .env -- gitignored). Free key: tiingo.com')
    return k                                   # never printed, never written to any output


class RateLimited(Exception):
    """Tiingo said no. The run stops and the manifest is saved so the next one resumes."""


def _get(url, headers=None, timeout=90):
    req = urllib.request.Request(url, headers=dict({'User-Agent': UA}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:400]
        except Exception:
            pass
        if e.code in (429, 403):
            raise RateLimited(f'HTTP {e.code}: {body}')
        raise


# --------------------------------------------------------- Tiingo ticker manifest

def supported_tickers(refresh=False):
    """Tiingo's public symbol manifest (NO API key needed -- verified 2026-09-14).

    Gives us, per symbol: exchange (which is how we know NYSE/AMEX vs Nasdaq for the
    Shumway delisting haircut in pit_panel.py) and the symbol's own start/end dates, which
    is how we refuse to join a price series that does not bracket a membership span."""
    os.makedirs(OUT_DIR, exist_ok=True)
    if refresh or not os.path.exists(TICKER_META):
        print('Fetching Tiingo supported_tickers.zip (no key required) ...')
        z = zipfile.ZipFile(io.BytesIO(_get(TIINGO_TICKERS_URL, timeout=180)))
        with z.open(z.namelist()[0]) as f, open(TICKER_META, 'w', newline='') as out:
            out.write(f.read().decode('utf-8'))
    meta = {}
    with open(TICKER_META) as f:
        for r in csv.DictReader(f):
            if r['assetType'] not in ('Stock', 'ETF') or r['priceCurrency'] != 'USD':
                continue
            if not r['startDate']:
                continue
            t = r['ticker'].upper()
            prev = meta.get(t)
            # Keep the entry with the LONGEST history: Tiingo lists some symbols more than
            # once (different exchanges / re-listings) and the long one is the real series.
            if prev is None or r['startDate'] < prev['startDate']:
                meta[t] = r
    return meta


# ---------------------------------------------------------------- company model

def _d(s):
    return datetime.date.fromisoformat(s) if s else None


def rename_chain(ticker, renames, limit=8):
    """[ticker, next, next, ...] following the rename map. The map contains a genuine cycle
    (FISV -> FI -> FISV), so this both bounds the walk and stops on a revisit."""
    chain, seen, cur = [ticker], {ticker}, ticker
    while cur in renames and len(chain) < limit:
        cur = renames[cur]
        if cur in seen:
            break
        seen.add(cur)
        chain.append(cur)
    return chain


def _candidates(ticker, renames):
    """Every symbol Tiingo might carry this company's series under."""
    out = []
    for t in rename_chain(ticker, renames):
        for v in (t, t.replace('.', '-')):
            if v not in out:
                out.append(v)
    return out


def build_companies(membership=None, renames=None, meta=None):
    """Group membership spans into COMPANIES and pick one Tiingo symbol for each.

    One column per company, not per ticker: a rename (ABC -> COR) is not an economic exit,
    so its two spans belong to one price series (design doc §2.3 class D). The company key is
    the terminal symbol of the rename chain; the *price* symbol is whichever candidate in the
    chain Tiingo covers best, which is not always the terminal one (PSKY exists but only from
    2025, while PARA carries 2006-2025 -- picking the terminal symbol blindly would throw
    away twenty years of history).

    Returns [{key, price_symbol, candidates, spans, first, last, era, months}] sorted into
    fetch order."""
    membership = membership if membership is not None else load_membership()
    renames = renames if renames is not None else load_renames()
    meta = meta if meta is not None else supported_tickers()

    groups = collections.OrderedDict()
    for r in membership:
        key = rename_chain(r['ticker'], renames)[-1]
        key = key.replace('.', '-')
        groups.setdefault(key, {'key': key, 'spans': [], 'candidates': []})
        groups[key]['spans'].append(r)
        for c in _candidates(r['ticker'], renames):
            if c not in groups[key]['candidates']:
                groups[key]['candidates'].append(c)

    out = []
    for g in groups.values():
        first = min(_d(s['start_date']) for s in g['spans'])
        last = max((_d(s['end_date']) or TODAY) for s in g['spans'])
        # Best candidate = the one whose Tiingo history covers the most of [first, last].
        best, best_cov = None, -1
        for c in g['candidates']:
            m = meta.get(c)
            if not m:
                continue
            ts, te = _d(m['startDate']), (_d(m['endDate']) or TODAY)
            cov = (min(te, last) - max(ts, first)).days
            if cov > best_cov:
                best, best_cov = c, cov
        # Months of membership inside the primary window -- the fetch priority.
        months = 0
        for s in g['spans']:
            a, b = max(_d(s['start_date']), ERA_START), (_d(s['end_date']) or TODAY)
            if b > a:
                months += (b - a).days / 30.44
        g.update({'price_symbol': best, 'first': first.isoformat(), 'last': last.isoformat(),
                  'era': '2009+' if months > 0 else 'pre2009', 'months': round(months, 1)})
        out.append(g)
    out.sort(key=lambda g: (0 if g['era'] == '2009+' else 1, -g['months'], g['key']))
    return out


# --------------------------------------------------------------------- fetching

def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST) as f:
            return json.load(f)
    return {'updated': None, 'symbols': {}}


def save_manifest(man):
    man['updated'] = datetime.datetime.now().isoformat(timespec='seconds')
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(MANIFEST, 'w') as f:
        json.dump(man, f, indent=1, sort_keys=True)


def fetch_symbol(sym, key):
    """Full adjusted daily history for one symbol -> DataFrame, or None if Tiingo has none.

    ADJUSTED fields throughout (adjOpen/High/Low/Close/Volume): splits and dividends must be
    folded in or every return is wrong. Design doc §3.6 -- adjustments computed today are
    correct arithmetic, not lookahead."""
    # format=csv, not json: same data at ~55% of the bytes, and the free tier has a 1 GB/mo
    # bandwidth cap that a 500-symbol run of 30-year histories would otherwise threaten.
    url = (TIINGO_PRICES.format(sym=urllib.parse.quote(sym))
           + f'?startDate={HISTORY_START}&format=csv')
    raw = _get(url, headers={'Authorization': f'Token {key}'})
    text = raw.decode('utf-8').strip()
    # Tiingo signals throttling with HTTP *200* and a plain-text body, not a 429. Missing
    # this check silently records hundreds of live tickers as "no data" -- which is exactly
    # what it did on the first run of this script.
    if text.lower().startswith('error') or 'allocation' in text[:200].lower():
        raise RateLimited(text[:160])
    if not text or '\n' not in text:
        return None
    df = pd.read_csv(io.StringIO(text))
    if df.empty or 'adjClose' not in df.columns:
        return None
    df['Date'] = pd.to_datetime(df['date']).dt.normalize()
    out = pd.DataFrame({
        'Date': df['Date'],
        'open': df['adjOpen'], 'high': df['adjHigh'], 'low': df['adjLow'],
        'close': df['adjClose'], 'volume': df['adjVolume'],
    }).dropna(subset=['close']).set_index('Date').sort_index()
    return out[~out.index.duplicated(keep='last')]


def price_path(sym):
    return os.path.join(OUT_DIR, f'{sym}.csv')


def run_fetch(companies, max_new, key, sleep=REQ_SLEEP, retry_wait=600, max_waits=0):
    """Pull the queue, newest-era first, stopping at the monthly cap.

    Tiingo's free tier throttles on TWO axes: ~200 requests per rolling hour, and 500 unique
    symbols per calendar month. The hourly one is what a 500-symbol run hits first, so when
    it fires we either stop cleanly (max_waits=0) or sleep and retry the SAME symbol
    (max_waits>0). Nothing is ever recorded as "no data" because of a throttle."""
    man = load_manifest()
    syms = man['symbols']
    month = TODAY.strftime('%Y-%m')
    used = sum(1 for v in syms.values() if v.get('first_fetch_month') == month)
    budget = min(max_new, MAX_NEW_SYMBOLS_PER_MONTH - used)
    print(f'Monthly cap {MAX_NEW_SYMBOLS_PER_MONTH}: {used} symbol(s) already used in '
          f'{month}; this run may fetch {max(budget, 0)}.')
    if budget <= 0:
        print('Monthly symbol budget exhausted -- re-run next calendar month to continue.')
        return man

    queue = []
    for sym in BENCHMARKS:
        if syms.get(sym, {}).get('status') != 'fetched':
            queue.append((sym, 'benchmark', None))
    for g in companies:
        sym = g['price_symbol']
        if sym is None:
            # Tiingo's manifest has no entry for ANY symbol in this company's rename chain.
            # Record it so coverage.json can count it instead of it vanishing quietly.
            syms.setdefault(g['key'], {})
            syms[g['key']].update({'status': 'missing_no_tiingo_data', 'company': g['key'],
                                   'checked': TODAY.isoformat(),
                                   'note': 'no symbol in the rename chain is in Tiingo'})
            continue
        if syms.get(sym, {}).get('status') == 'fetched':
            continue
        queue.append((sym, g['era'], g['key']))

    print(f'{len(queue)} symbol(s) pending; fetching up to {budget}.', flush=True)
    done = fail = waits = 0
    try:
        for sym, era, company in queue[:budget]:
            errored = False
            while True:
                try:
                    df = fetch_symbol(sym, key)
                    break
                except RateLimited as e:
                    if waits >= max_waits:
                        print(f'\nRATE LIMITED at {sym} after {done} fetches: {e}')
                        print('Manifest saved -- re-run later to resume exactly here.',
                              flush=True)
                        raise
                    waits += 1
                    print(f'  throttled at {sym} ({done} fetched); sleeping {retry_wait}s '
                          f'[wait {waits}/{max_waits}]', flush=True)
                    save_manifest(man)
                    time.sleep(retry_wait)
                except Exception as e:                # noqa: BLE001 - one bad symbol, not a run
                    syms[sym] = {'status': 'error', 'company': company,
                                 'checked': TODAY.isoformat(), 'note': type(e).__name__}
                    fail += 1
                    errored = True
                    break
            if errored:
                continue
            if df is None or df.empty:
                # Still a unique symbol Tiingo counted against the monthly allowance, so it
                # is stamped with the month exactly like a successful pull.
                syms[sym] = {'status': 'missing_no_tiingo_data', 'company': company,
                             'checked': TODAY.isoformat(), 'first_fetch_month': month}
                fail += 1
            else:
                df.to_csv(price_path(sym))
                syms[sym] = {'status': 'fetched', 'company': company, 'era': era,
                             'rows': int(len(df)),
                             'start': df.index[0].date().isoformat(),
                             'end': df.index[-1].date().isoformat(),
                             'fetched': TODAY.isoformat(),
                             'first_fetch_month': month}
                done += 1
            if done and done % 25 == 0:
                save_manifest(man)
                print(f'  ... {done} fetched ({sym} {era})', flush=True)
            time.sleep(sleep)
    finally:
        save_manifest(man)
    print(f'Fetched {done} symbol(s); {fail} had no Tiingo data.')
    return man


# --------------------------------------------------------------------- coverage

def load_prices(sym):
    p = price_path(sym)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, parse_dates=['Date'], index_col='Date')
    return df if len(df) else None


def build_coverage(companies, man=None):
    """Per membership SPAN: priced_full | priced_partial | missing, judged against the price
    file we ACTUALLY have on disk (not against Tiingo's manifest promises).

    priced_full    = the series covers the whole span (<= 10 calendar days of slack at each
                     end, for holidays and for an acquisition that stops trading mid-week).
    priced_partial = some of the span is priced.
    missing        = the vendor genuinely has nothing (a dead name) -> pit_panel patches it.
    pending_fetch  = we have simply not spent a symbol from this month's budget on it yet.
                     pit_panel holds these OUT of the universe rather than imputing them:
                     conflating the two would corrupt the panel for a reason that has
                     nothing to do with survivorship."""
    man = man or load_manifest()
    spans, per_company = [], {}
    cache = {}
    for g in companies:
        sym = g['price_symbol']
        if sym is not None and sym not in cache:
            cache[sym] = load_prices(sym)
        px = cache.get(sym)
        rng = None
        if px is not None:
            rng = (px.index[0].date(), px.index[-1].date())
        per_company[g['key']] = {'price_symbol': sym, 'range': [str(rng[0]), str(rng[1])] if rng else None}
        st = man['symbols'].get(sym, {}).get('status') if sym else 'missing_no_tiingo_data'
        for s in g['spans']:
            a, b = _d(s['start_date']), (_d(s['end_date']) or TODAY)
            if rng is None:
                status = 'missing' if st in ('missing_no_tiingo_data', 'error') else 'pending_fetch'
            else:
                ts, te = rng
                if ts <= a + datetime.timedelta(days=10) and te >= b - datetime.timedelta(days=10):
                    status = 'priced_full'
                elif te >= a and ts <= b:
                    status = 'priced_partial'
                else:
                    status = 'missing'            # series exists but does NOT bracket the span
            spans.append({'ticker': s['ticker'], 'company': g['key'], 'price_symbol': sym,
                          'start_date': s['start_date'], 'end_date': s['end_date'],
                          'exit_class': s['exit_class'], 'status': status,
                          'in_2009_window': bool(b >= ERA_START)})
    cov = {'built': TODAY.isoformat(), 'membership_csv': MEMBERSHIP_CSV,
           'n_spans': len(spans), 'companies': per_company, 'spans': spans}
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(COVERAGE, 'w') as f:
        json.dump(cov, f, indent=1)
    return cov


def coverage_summary(cov, window_only=True):
    rows = [s for s in cov['spans'] if s['in_2009_window'] or not window_only]
    by = collections.Counter((s['exit_class'], s['status']) for s in rows)
    classes = ['A', 'B', 'C', 'D', 'active']
    statuses = ['priced_full', 'priced_partial', 'missing', 'pending_fetch']
    lines = [f"  {'exit class':<10}" + ''.join(f'{s:>16}' for s in statuses) + f"{'total':>8}"]
    lines.append('  ' + '-' * 82)
    for c in classes:
        tot = sum(by[(c, s)] for s in statuses)
        if not tot:
            continue
        lines.append(f'  {c:<10}' + ''.join(f'{by[(c, s)]:>16d}' for s in statuses) + f'{tot:>8d}')
    tot = len(rows)
    lines.append('  ' + '-' * 82)
    lines.append(f"  {'ALL':<10}" + ''.join(f'{sum(by[(c, s)] for c in classes):>16d}'
                                            for s in statuses) + f'{tot:>8d}')
    priced = sum(by[(c, s)] for c in classes for s in ('priced_full', 'priced_partial'))
    pend = sum(by[(c, 'pending_fetch')] for c in classes)
    lines.append(f'  priced (full or partial): {priced}/{tot} = {priced / tot * 100:.1f}%'
                 f'   |  not yet fetched: {pend} ({pend / tot * 100:.1f}%)')
    return '\n'.join(lines)


# ------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--max-new', type=int, default=MAX_NEW_SYMBOLS_PER_MONTH,
                    help='cap NEW symbols this run (the monthly cap still applies)')
    ap.add_argument('--plan', action='store_true', help='print the queue and exit')
    ap.add_argument('--coverage', action='store_true', help='rebuild coverage.json only')
    ap.add_argument('--refresh-tickers', action='store_true',
                    help='re-download Tiingo supported_tickers.zip')
    ap.add_argument('--retry-wait', type=int, default=600,
                    help='seconds to sleep when Tiingo throttles the hourly allocation')
    ap.add_argument('--max-waits', type=int, default=0,
                    help='how many times to sleep-and-retry before giving up (0 = stop at '
                         'the first throttle and resume on a later run)')
    args = ap.parse_args()

    if not os.path.exists(MEMBERSHIP_CSV):
        sys.exit(f'{MEMBERSHIP_CSV} not found -- run fetch_membership.py first.')
    meta = supported_tickers(refresh=args.refresh_tickers)
    companies = build_companies(meta=meta)
    n_era = sum(1 for g in companies if g['era'] == '2009+')
    n_sym = sum(1 for g in companies if g['price_symbol'])
    print(f'{len(companies)} companies ({n_era} with 2009+ membership); '
          f'{n_sym} have a Tiingo symbol, {len(companies) - n_sym} have none.')

    if args.plan:
        man = load_manifest()
        pend = [g for g in companies if g['price_symbol']
                and man['symbols'].get(g['price_symbol'], {}).get('status') != 'fetched']
        print(f'{len(pend)} pending. First 20 of the queue:')
        for g in pend[:20]:
            print(f"   {g['price_symbol']:<8} {g['era']:<7} {g['months']:>6.1f} eligible-months "
                  f"({g['first']} -> {g['last']})")
        return
    if not args.coverage:
        run_fetch(companies, args.max_new, api_key(),
                  retry_wait=args.retry_wait, max_waits=args.max_waits)

    cov = build_coverage(companies)
    print('\nSPAN COVERAGE (spans overlapping the 2009+ window):')
    print(coverage_summary(cov))
    print(f'\nWrote {COVERAGE} and {MANIFEST}')


if __name__ == '__main__':
    main()
