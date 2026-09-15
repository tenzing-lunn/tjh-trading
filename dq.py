"""I1.2: fail-closed data admission, with exchange-calendar session exclusions.

Run .venv/bin/python dq.py to inspect minute caches and daily CSVs.
Minute certificates bind exclusions to SHA-256 file contents. load_intraday()
requires a current certificate and returns separate sessions, never a compressed
series that could silently earn returns across excluded days.
"""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

VERSION = 1
MIN_COVERAGE = .60
MAX_MINUTE_RETURN = .20


class QualityError(ValueError):
    pass


@lru_cache(maxsize=16)
def schedule(start, end):
    import exchange_calendars as xc
    cal = xc.get_calendar('XNYS', start=start, end=end)
    frame = cal.schedule[['open', 'close']].copy()
    # exchange-calendars 4.5 (last release for Python 3.9) predates this closure.
    # NYSE notice: https://www.nyse.com/publicdocs/nyse/markets/american-options/
    # rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf
    frame = frame.drop(pd.Timestamp('2025-01-09'), errors='ignore')
    frame.index = frame.index.strftime('%Y-%m-%d')
    return frame


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def invalid_ohlcv(df):
    required = ['open', 'high', 'low', 'close', 'volume']
    if not set(required).issubset(df.columns):
        raise QualityError('Missing required OHLCV columns')
    x = df[required].astype(float)
    return (~np.isfinite(x).all(axis=1) | (x[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
            | (x.volume <= 0) | (x.high < x[['open', 'close', 'low']].max(axis=1))
            | (x.low > x[['open', 'close', 'high']].min(axis=1)))


def longest_run(mask):
    best = run = 0
    for missing in mask:
        run = run + 1 if missing else 0
        best = max(best, run)
    return best


def validate_daily(df, expected_start=None):
    """Validate after existing leading pre-IPO trimming; never silently repair rows."""
    if len(df) < 2:
        raise QualityError('Fewer than two observed daily bars')
    idx = pd.DatetimeIndex(df.index)
    if idx.hasnans or idx.has_duplicates or not idx.is_monotonic_increasing:
        raise QualityError('Invalid, duplicate or unordered timestamps')
    if any(idx != idx.normalize()):
        raise QualityError('Intraday CSVs require the checked session loader')
    if invalid_ohlcv(df).any():
        raise QualityError('Invalid OHLCV or interior zero-volume bars')
    dates = idx.strftime('%Y-%m-%d')
    start = expected_start or dates[0]
    sessions = schedule(str(start), dates[-1])
    if dates[0] > sessions.index[0]:
        raise QualityError('History starts after the declared start')
    if not set(dates).issubset(sessions.index):
        raise QualityError('Daily bars on non-trading dates')
    if longest_run(~sessions.index.isin(dates)) > 3:
        raise QualityError('More than three missing trading sessions')


def inspect_sessions(df, sessions):
    """Calendar-aware minute screen. Empty sessions are explicitly represented."""
    data = df.copy()
    data['timestamp'] = pd.to_datetime(data.timestamp, utc=True)
    if data.timestamp.isna().any():
        raise QualityError('Invalid minute timestamp')
    local = data.timestamp.dt.tz_convert('America/New_York').dt.tz_localize(None)
    # NumPy formats dates without a per-row timezone strftime call.
    data['day'] = local.to_numpy().astype('datetime64[D]').astype(str)
    data = data.join(sessions.rename(columns={'open': 'session_open', 'close': 'session_close'}), on='day')
    data = data[(data.timestamp >= data.session_open) & (data.timestamp < data.session_close)].copy()
    grouped = data.groupby('day', sort=False)
    dt = grouped.timestamp.diff()
    data['duplicate_timestamp'] = data.timestamp.duplicated(keep=False)
    data['unordered_timestamps'] = dt < pd.Timedelta(0)
    data['non_minute_timestamp'] = data.timestamp != data.timestamp.dt.floor('min')
    data['invalid_ohlcv'] = invalid_ohlcv(data)
    data['extreme_1min_return'] = ((data.close / grouped.close.shift() - 1).abs() > MAX_MINUTE_RETURN) & (dt == pd.Timedelta(minutes=1))
    flags = ['duplicate_timestamp', 'unordered_timestamps', 'non_minute_timestamp',
             'invalid_ohlcv', 'extreme_1min_return']
    counts = data.groupby('day').size()
    failures = data.groupby('day')[flags].any()
    rows = []
    for day, session in sessions.iterrows():
        expected = int((session['close'] - session['open']).total_seconds() / 60)
        observed = int(counts.get(day, 0))
        reasons = []
        if observed < expected * MIN_COVERAGE:
            reasons.append('missing_session' if observed == 0 else 'coverage_below_60pct')
        if day in failures.index:
            reasons.extend(flag for flag in flags if failures.loc[day, flag])
        rows.append({'day': day, 'expected': expected, 'observed': observed,
                     'status': 'EXCLUDE' if reasons else 'PASS', 'reasons': reasons,
                     'open': session['open'].isoformat(), 'close': session['close'].isoformat()})
    return rows


def inspect_symbol(symbol, root=Path('intraday')):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    months = manifest[symbol]
    paths = sorted((root / symbol).glob('*.parquet'))
    if not months or not paths:
        raise QualityError('Missing manifest or parquet history')
    if any(r.get('status') != 'ok' for r in months.values()):
        raise QualityError('Unverified empty or failed month; rerun fetch_intraday.py')
    if {p.stem for p in paths} != set(months):
        raise QualityError('Manifest and files differ')
    frames, hashes = [], {}
    for path in paths:
        rec = months[path.stem]
        if (rec.get('source'), rec.get('feed'), rec.get('adjustment')) != ('alpaca', 'sip', 'all'):
            raise QualityError('Unexpected source/feed/adjustment')
        frame = pd.read_parquet(path)
        if len(frame) != rec['rows'] or int(frame.regular.sum()) != rec['regular_rows']:
            raise QualityError(f'Manifest count mismatch: {path.name}')
        frames.append(frame)
        hashes[path.name] = sha256(path)
    data = pd.concat(frames, ignore_index=True)
    retrieval = pd.Timestamp(months[max(months)]['retrieval_time'])
    end = retrieval.tz_convert('America/New_York').strftime('%Y-%m-%d')
    sessions = schedule('2016-01-01', end)
    # Exclude the current, not-yet-complete session from the expected history.
    sessions = sessions[sessions['close'] <= retrieval - pd.Timedelta(minutes=16)]
    rows = inspect_sessions(data, sessions)
    first_observed = next((r['day'] for r in rows if r['observed']), None)
    missing = [r['observed'] == 0 for r in rows]
    report = {'version': VERSION, 'symbol': symbol, 'files': hashes,
              'manifest_sha256': sha256(root / 'manifest.json'),
              'min_coverage': MIN_COVERAGE, 'max_minute_return': MAX_MINUTE_RETURN,
              'start_late': first_observed != sessions.index[0],
              'longest_missing_session_run': longest_run(missing), 'sessions': rows}
    target = root / '_quality' / f'{symbol}.json'
    target.parent.mkdir(exist_ok=True)
    tmp = target.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, indent=2))
    tmp.replace(target)
    return report


def load_intraday(symbol, start=None, end=None, root=Path('intraday')):
    """Return {session_date: OHLCV frame}; require unchanged inspected source files.

    Excluded dates are absent from this mapping, explicitly listed in the certificate.
    The Phase 2 engine must consume session boundaries; do not concat and pct_change.
    """
    root = Path(root)
    path = root / '_quality' / f'{symbol}.json'
    if not path.exists():
        raise QualityError('Unchecked minute data; run dq.py first')
    report = json.loads(path.read_text())
    if report['version'] != VERSION or report['manifest_sha256'] != sha256(root / 'manifest.json'):
        raise QualityError('Stale quality certificate; rerun dq.py')
    if report['start_late']:
        raise QualityError('History begins after the declared vendor start')
    paths = sorted((root / symbol).glob('*.parquet'))
    if {p.name for p in paths} != set(report['files']):
        raise QualityError('Minute file set changed after inspection')
    for file in paths:
        if sha256(file) != report['files'][file.name]:
            raise QualityError(f'Changed minute data: {file.name}; rerun dq.py')
    admitted = [r for r in report['sessions'] if r['status'] == 'PASS'
                and (start is None or r['day'] >= str(start)) and (end is None or r['day'] <= str(end))]
    if not admitted:
        raise QualityError('No admitted sessions in requested range')
    # Load only overlapping UTC-month partitions (New York session is in one UTC day).
    months = {r['day'][:7] for r in admitted}
    data = pd.concat([pd.read_parquet(p) for p in paths if p.stem in months], ignore_index=True)
    data['timestamp'] = pd.to_datetime(data.timestamp, utc=True)
    data = data.set_index('timestamp').sort_index()
    return {r['day']: data[(data.index >= r['open']) & (data.index < r['close'])].drop(columns='regular', errors='ignore')
            for r in admitted}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--symbols', nargs='+')
    parser.add_argument('--daily-only', action='store_true')
    args = parser.parse_args()
    failures = 0
    if not args.daily_only:
        symbols = args.symbols or sorted(json.loads(Path('intraday/manifest.json').read_text()))
        for symbol in symbols:
            try:
                report = inspect_symbol(symbol)
                excluded = sum(r['status'] == 'EXCLUDE' for r in report['sessions'])
                print(f'{symbol:6s} PASS {len(report["sessions"])-excluded} sessions; EXCLUDE {excluded}; '
                      f'longest missing run {report["longest_missing_session_run"]}', flush=True)
                failures += int(report['start_late'])
            except (QualityError, ValueError, KeyError) as exc:
                print(f'{symbol:6s} EXCLUDE {exc}', flush=True)
                failures += 1
    for path in sorted(Path('realdata').glob('*.csv')):
        try:
            from data import load_csv
            frame = load_csv(path, warn=False)
            print(f'{path.stem:6s} daily PASS {len(frame)} bars', flush=True)
        except (ValueError, KeyError) as exc:
            print(f'{path.stem:6s} daily EXCLUDE {exc}', flush=True)
            failures += 1
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
