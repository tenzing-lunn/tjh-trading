"""Calendar, fail-closed, and session-exclusion regressions."""
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from dq import (QualityError, inspect_sessions, inspect_symbol, load_intraday,
                schedule, sha256, validate_daily)


def bars(start, n):
    return pd.DataFrame({'timestamp': pd.date_range(start, periods=n, freq='min'),
                         'open': 100., 'high': 101., 'low': 99., 'close': 100., 'volume': 10.})


def daily_bars(closes):
    prices = np.asarray(closes, dtype=float)
    return pd.DataFrame({'open': prices, 'high': prices, 'low': prices,
                         'close': prices, 'volume': 10.},
                        index=pd.date_range('2024-12-02', periods=len(prices), freq='B'))


class QualityTests(unittest.TestCase):
    def test_early_close_and_dst(self):
        sessions = schedule('2024-11-29', '2024-12-02')
        frame = bars('2024-11-29 14:30:00+00:00', 390)
        result = inspect_sessions(frame, sessions)
        self.assertEqual((result[0]['expected'], result[0]['observed'], result[0]['status']), (210, 210, 'PASS'))
        self.assertEqual(result[1]['reasons'], ['missing_session'])
        dst = schedule('2024-03-08', '2024-03-11')
        self.assertEqual(dst.iloc[0]['open'].hour, 14)
        self.assertEqual(dst.iloc[-1]['open'].hour, 13)

    def test_closure_and_short_day_are_not_confused(self):
        self.assertNotIn('2025-01-09', schedule('2025-01-08', '2025-01-10').index)
        sessions = schedule('2024-12-02', '2024-12-03')
        frame = pd.concat([bars('2024-12-02 14:30:00+00:00', 1),
                           bars('2024-12-03 14:30:00+00:00', 390)], ignore_index=True)
        result = inspect_sessions(frame, sessions)
        self.assertEqual([r['status'] for r in result], ['EXCLUDE', 'PASS'])

    def test_extreme_move_and_duplicates_exclude_the_day(self):
        frame = bars('2024-12-02 14:30:00+00:00', 390)
        frame.loc[10, ['open', 'high', 'low', 'close']] *= 1.3
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        reasons = inspect_sessions(frame, schedule('2024-12-02', '2024-12-03'))[0]['reasons']
        self.assertIn('extreme_1min_return', reasons)
        self.assertIn('duplicate_timestamp', reasons)

    def test_single_bar_and_long_gap_daily_rejected(self):
        frame = bars('2024-12-02', 1).set_index('timestamp')
        with self.assertRaises(QualityError):
            validate_daily(frame)
        frame = pd.concat([frame, frame.set_axis(pd.DatetimeIndex(['2024-12-20']))])
        with self.assertRaisesRegex(QualityError, 'missing trading sessions'):
            validate_daily(frame)

    def test_daily_interday_return_above_audit_threshold_is_rejected(self):
        for closes in ([100., 160.000001], [100., 39.999999]):
            with self.subTest(closes=closes), self.assertRaisesRegex(
                    QualityError, 'greater than 60%'):
                validate_daily(daily_bars(closes))

    def test_daily_interday_return_at_audit_threshold_is_accepted(self):
        for closes in ([100., 160.], [100., 40.],
                       [10., 16.], [10., 4.],
                       [1., 1.6], [1., .4]):
            with self.subTest(closes=closes):
                validate_daily(daily_bars(closes))

    def test_nonfinite_daily_return_is_rejected(self):
        frame = daily_bars([np.finfo(float).tiny, np.finfo(float).max])
        with self.assertRaisesRegex(QualityError, 'Non-finite'):
            validate_daily(frame)

    def test_four_missing_sessions_reject_entire_minute_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'SPY').mkdir()
            frame = pd.concat([
                bars('2016-01-04 14:30:00+00:00', 390),
                bars('2016-01-11 14:30:00+00:00', 390),
                bars('2016-01-12 14:30:00+00:00', 390),
            ], ignore_index=True)
            frame['regular'] = True
            path = root / 'SPY/2016-01.parquet'
            frame.to_parquet(path)
            manifest = {'SPY': {'2016-01': {
                'status': 'ok', 'source': 'alpaca', 'feed': 'sip', 'adjustment': 'all',
                'rows': len(frame), 'regular_rows': len(frame),
                'retrieval_time': '2016-01-12T21:30:00+00:00',
            }}}
            (root / 'manifest.json').write_text(json.dumps(manifest))

            with self.assertRaisesRegex(
                    QualityError, r'More than three consecutive missing trading sessions \(4\)'):
                inspect_symbol('SPY', root=root)
            self.assertFalse((root / '_quality/SPY.json').exists())

    def test_loader_rejects_legacy_certificate_with_long_session_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'SPY').mkdir()
            (root / '_quality').mkdir()
            (root / 'manifest.json').write_text('{}')
            frame = bars('2016-01-04 14:30:00+00:00', 390)
            path = root / 'SPY/2016-01.parquet'
            frame.to_parquet(path)
            sessions = [
                {'day': f'2016-01-{day:02d}', 'observed': 390 if day in (4, 11) else 0,
                 'status': 'PASS' if day in (4, 11) else 'EXCLUDE', 'reasons': [],
                 'open': '2016-01-04T14:30:00+00:00',
                 'close': '2016-01-04T21:00:00+00:00'}
                for day in (4, 5, 6, 7, 8, 11)
            ]
            report = {'version': 1, 'manifest_sha256': sha256(root / 'manifest.json'),
                      'start_late': False, 'files': {path.name: sha256(path)},
                      'sessions': sessions}
            (root / '_quality/SPY.json').write_text(json.dumps(report))

            with self.assertRaisesRegex(QualityError, 'entire symbol excluded'):
                load_intraday('SPY', root=root)

    def test_unchecked_or_stale_cache_cannot_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaisesRegex(QualityError, 'Unchecked'):
                load_intraday('SPY', root=root)
            (root / '_quality').mkdir()
            (root / 'manifest.json').write_text('{}')
            (root / '_quality/SPY.json').write_text(json.dumps({'version': 1, 'manifest_sha256': 'wrong'}))
            with self.assertRaisesRegex(QualityError, 'Stale'):
                load_intraday('SPY', root=root)

    def test_session_loader_excludes_bad_day_and_detects_changed_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'SPY').mkdir()
            (root / '_quality').mkdir()
            (root / 'manifest.json').write_text('{}')
            frame = pd.concat([bars('2024-12-02 14:30:00+00:00', 1),
                               bars('2024-12-03 14:30:00+00:00', 390)], ignore_index=True)
            path = root / 'SPY/2024-12.parquet'
            frame.to_parquet(path)
            report = {'version': 1, 'manifest_sha256': sha256(root / 'manifest.json'),
                      'start_late': False, 'files': {path.name: sha256(path)},
                      'sessions': inspect_sessions(frame, schedule('2024-12-02', '2024-12-03'))}
            (root / '_quality/SPY.json').write_text(json.dumps(report))
            admitted = load_intraday('SPY', root=root)
            self.assertEqual(list(admitted), ['2024-12-03'])
            self.assertEqual(len(admitted['2024-12-03']), 390)
            frame.loc[0, 'close'] = 101
            frame.to_parquet(path)
            with self.assertRaisesRegex(QualityError, 'Changed minute data'):
                load_intraday('SPY', root=root)

    def test_daily_file_boundary_rejects_single_bar(self):
        from data import load_csv
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'wrk.csv'
            bars('2024-12-02', 1).set_index('timestamp').to_csv(path)
            with self.assertRaisesRegex(QualityError, 'Fewer than two'):
                load_csv(path)


if __name__ == '__main__':
    unittest.main()
