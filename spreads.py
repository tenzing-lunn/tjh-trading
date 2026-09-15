"""I1.4: reproducible, read-only SIP quote sampling; no order endpoints.

python3 spreads.py --fetch  # resume the fixed plan; keys are loaded locally
python3 spreads.py --backfill  # unchanged sampling times; recover missing NBBO up to 60s old
python3 spreads.py          # rebuild tables from a completed cache, no network

Twenty evenly spaced full SPY sessions per year, through the previous UTC day.
One deterministic uniform timestamp in each open/mid/close bucket per day.
Initially query one second and retain the LAST quote update per symbol. The fixed
backfill amendment looks back up to 60 seconds for missing updates only, clamped
to the bucket start. This estimates NBBO at a uniform time rather than weighting
by quote update count. No update is missing data, never a zero spread. These
sparse snapshots estimate quoted spread, not fills,
opening-auction costs, slippage, capacity, or the worst spread during a session.
"""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockQuotesRequest

from fetch_intraday import ThrottledStockClient, _load_dotenv, universe_symbols

ROOT = Path('research_data/spread_samples')
BUCKETS = {'open': (570, 600), 'mid': (600, 930), 'close': (930, 960)}
VERSION = 1


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
    tmp.replace(path)


def make_plan(symbols, cutoff):
    days = duckdb.sql("""SELECT timezone('America/New_York',timestamp)::DATE AS day,
        count(DISTINCT timestamp) AS n FROM read_parquet('intraday/SPY/*.parquet')
        WHERE regular GROUP BY day HAVING n >= 380 ORDER BY day""").df()
    days = pd.to_datetime(days['day'])
    days = days[days < pd.Timestamp(cutoff)]
    if days.empty:
        raise ValueError('No eligible SPY history for the quote sample plan')
    from dq import schedule
    calendar = schedule(days.iloc[0].strftime('%Y-%m-%d'), days.iloc[-1].strftime('%Y-%m-%d'))
    full_days = calendar.index[(calendar['close'] - calendar['open']) == pd.Timedelta(minutes=390)]
    days = days[days.dt.strftime('%Y-%m-%d').isin(full_days)]
    windows = []
    for year in sorted(days.dt.year.unique()):
        year_days = days[days.dt.year == year].tolist()
        selected = np.linspace(0, len(year_days) - 1, min(20, len(year_days)), dtype=int)
        for idx in selected:
            day = year_days[idx].strftime('%Y-%m-%d')
            for bucket, (lo, hi) in BUCKETS.items():
                # Fixed seed from the date and bucket; independent of prices/spreads.
                seed = int.from_bytes(hashlib.sha256(f'{VERSION}:{day}:{bucket}'.encode()).digest()[:8], 'big')
                offset = int(np.random.default_rng(seed).integers(lo * 60, hi * 60 - 1))
                start = pd.Timestamp(day, tz='America/New_York') + pd.Timedelta(seconds=offset)
                windows.append({'day': day, 'bucket': bucket,
                                'start': start.tz_convert('UTC').isoformat(),
                                'end': (start + pd.Timedelta(seconds=1)).tz_convert('UTC').isoformat()})
    return {'version': VERSION, 'feed': 'sip', 'days_per_year': 20,
            'cutoff_exclusive': cutoff, 'symbols': sorted(symbols), 'windows': windows}


def quote_sample(quotes, start, end):
    """Do not cherry-pick the last VALID quote when the actual last quote is bad."""
    inside = [q for q in quotes if start <= q.timestamp < end]
    if not inside:
        return {'status': 'no_update', 'updates': 0}
    q = max(inside, key=lambda q: q.timestamp)
    bid, ask = float(q.bid_price), float(q.ask_price)
    bid_size, ask_size = float(q.bid_size), float(q.ask_size)
    rec = {'timestamp': q.timestamp.isoformat(), 'bid': bid, 'ask': ask,
           'bid_size': bid_size, 'ask_size': ask_size, 'updates': len(inside)}
    values = [bid, ask, bid_size, ask_size]
    if not all(math.isfinite(v) and v > 0 for v in values):
        return {'status': 'invalid_price_or_size', 'updates': len(inside)}
    if ask <= bid:
        rec['status'] = 'locked_or_crossed'
    else:
        rec.update(status='ok', half_spread_bps=(ask - bid) / (ask + bid) * 10000)
    return rec


def fetch_plan(plan, root, backfill=False):
    _load_dotenv()
    client = ThrottledStockClient(os.environ['APCA_API_KEY_ID'], os.environ['APCA_API_SECRET_KEY'])
    for i, window in enumerate(plan['windows']):
        path = root / f"{window['day']}-{window['bucket']}.json"
        cached = json.loads(path.read_text()) if path.exists() else None
        if cached and (not backfill or cached.get('backfill_complete')):
            continue
        if backfill and not cached:
            raise RuntimeError('Finish the original --fetch before --backfill')
        start, end = (datetime.fromisoformat(window[k]) for k in ('start', 'end'))
        symbols = plan['symbols']
        if backfill:
            symbols = [s for s, rec in cached['samples'].items() if rec['status'] == 'no_update']
            bucket_start = pd.Timestamp(window['day'], tz='America/New_York') + pd.Timedelta(minutes=BUCKETS[window['bucket']][0])
            start = max(pd.Timestamp(end) - pd.Timedelta(seconds=60), bucket_start).to_pydatetime()
            if not symbols:
                cached['backfill_complete'] = True
                atomic_json(path, cached)
                continue
        req = StockQuotesRequest(symbol_or_symbols=symbols, start=start, end=end,
                                 feed=DataFeed.SIP)
        try:
            quotes = client.get_stock_quotes(req).data
        except Exception as exc:
            # No headers, credentials or raw vendor exception text in logs.
            mode = '--backfill' if backfill else '--fetch'
            raise RuntimeError(f"Quote request failed ({type(exc).__name__}); resume with {mode}") from None
        samples = {sym: quote_sample(quotes.get(sym, []), start, end) for sym in symbols}
        for sample in samples.values():
            if 'timestamp' in sample:
                sample['quote_age_seconds'] = (end - datetime.fromisoformat(sample['timestamp'])).total_seconds()
        if backfill:
            cached['samples'].update(samples)
            cached.update(backfill_complete=True, backfill_symbols=symbols,
                          backfill_start=start.isoformat(),
                          backfill_retrieval_time=datetime.now(timezone.utc).isoformat())
            atomic_json(path, cached)
        else:
            atomic_json(path, {'window': window, 'source': 'alpaca', 'feed': 'sip',
                               'retrieval_time': datetime.now(timezone.utc).isoformat(), 'samples': samples})
        if (i + 1) % 15 == 0 or i + 1 == len(plan['windows']):
            print(f"Cached {i + 1}/{len(plan['windows'])} quote windows", flush=True)


def summarize(plan, root):
    records = []
    amendment_path = root.parent / 'backfill-plan.json'
    backfill_required = amendment_path.exists()
    if backfill_required and json.loads(amendment_path.read_text())['base_plan'] != root.name:
        raise ValueError('Backfill amendment refers to another sample plan')
    for window in plan['windows']:
        path = root / f"{window['day']}-{window['bucket']}.json"
        if not path.exists():
            raise RuntimeError(f'Incomplete sample plan: missing {path.name}; run --fetch')
        doc = json.loads(path.read_text())
        if backfill_required and not doc.get('backfill_complete'):
            raise RuntimeError('Incomplete backfill; resume --backfill before publishing tables')
        if doc['window'] != window or set(doc['samples']) != set(plan['symbols']):
            raise ValueError(f'Cache provenance mismatch: {path.name}')
        for sym, sample in doc['samples'].items():
            if 'timestamp' in sample:
                sample['quote_age_seconds'] = (datetime.fromisoformat(window['end']) - datetime.fromisoformat(sample['timestamp'])).total_seconds()
            records.append({'symbol': sym, 'bucket': window['bucket'],
                            'year': int(window['day'][:4]), 'day': window['day'], **sample})
    data = pd.DataFrame(records)
    data['half_spread_bps'] = pd.to_numeric(data.get('half_spread_bps', np.nan))
    def table(keys):
        rows = []
        for group, frame in data.groupby(keys):
            values = frame.loc[frame.status == 'ok', 'half_spread_bps'].dropna()
            row = dict(zip(keys, group if isinstance(group, tuple) else (group,)))
            row.update(expected=len(frame), valid=len(values),
                       coverage=len(values) / len(frame),
                       median_half_spread_bps=values.median(),
                       p95_half_spread_bps=values.quantile(.95),
                       mean_half_spread_bps=values.mean())
            rows.append(row)
        return pd.DataFrame(rows)
    overall, yearly = table(['symbol', 'bucket']), table(['symbol', 'year', 'bucket'])
    Path('research_data').mkdir(exist_ok=True)
    data.to_csv('research_data/spread_samples.csv', index=False)
    overall.to_csv('research_data/spreads.csv', index=False)
    yearly.to_csv('research_data/spreads_by_year.csv', index=False)
    atomic_json(Path('research_data/spreads_manifest.json'), {'plan_hash': root.name,
        'sampling_plan': plan, 'backfill_complete': backfill_required,
        'sample_statuses': data.status.value_counts().to_dict(),
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'files': ['spreads.csv', 'spreads_by_year.csv', 'spread_samples.csv']})
    print(overall.to_string(index=False))
    print('Sample statuses:', data.status.value_counts().to_dict())
    print('Year/buckets with coverage <80%:', int((yearly.coverage < .8).sum()))
    if 'quote_age_seconds' in data:
        print('Quote age seconds:', data.quote_age_seconds.quantile([.5, .95, 1.]).to_dict())
    return overall, yearly


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--backfill', action='store_true', help='Resolve no-update snapshots with a fixed 60-second lookback')
    args = parser.parse_args()
    plan_path = ROOT / 'plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_text())
    else:
        plan = make_plan(universe_symbols(), datetime.now(timezone.utc).date().isoformat())
        atomic_json(plan_path, plan)  # freeze the design before requesting any quotes
    digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:16]
    root = ROOT / digest
    print(f'Fixed sample plan {digest}: {len(plan["windows"])} windows, {len(plan["symbols"])} symbols', flush=True)
    if args.backfill:
        atomic_json(ROOT / 'backfill-plan.json', {'base_plan': digest, 'lookback_seconds': 60,
            'only_status': 'no_update', 'clamp_to_bucket_open': True,
            'reason': 'Recover existing NBBO at unchanged sampling times when no quote updated in the original second'})
    if args.fetch or args.backfill:
        fetch_plan(plan, root, backfill=args.backfill)
    summarize(plan, root)


if __name__ == '__main__':
    main()
