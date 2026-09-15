"""Offline checks for quote selection, cost units, and incomplete evidence."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from spreads import fetch_plan, quote_sample, summarize


class SpreadTests(unittest.TestCase):
    start = datetime(2020, 1, 2, 15, tzinfo=timezone.utc)

    def quote(self, seconds=0, bid=99.99, ask=100.01, size=10):
        return SimpleNamespace(timestamp=self.start + timedelta(seconds=seconds),
                               bid_price=bid, ask_price=ask, bid_size=size, ask_size=size)

    def sample(self, quotes):
        return quote_sample(quotes, self.start, self.start + timedelta(seconds=1))

    def test_half_spread_units(self):
        self.assertAlmostEqual(self.sample([self.quote()])['half_spread_bps'], 1.)

    def test_latest_update_not_average_or_best_valid(self):
        record = self.sample([self.quote(), self.quote(.5, bid=100, ask=100)])
        self.assertEqual(record['status'], 'locked_or_crossed')
        self.assertNotIn('half_spread_bps', record)

    def test_missing_or_invalid_is_not_zero_cost(self):
        self.assertEqual(self.sample([self.quote(-1), self.quote(1)])['status'], 'no_update')
        self.assertEqual(self.sample([self.quote(size=0)])['status'], 'invalid_price_or_size')
        self.assertEqual(self.sample([self.quote(bid=float('nan'))])['status'], 'invalid_price_or_size')

    def test_incomplete_plan_cannot_publish_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, 'Incomplete sample plan'):
                summarize({'windows': [{'day': '2020-01-02', 'bucket': 'open'}]}, Path(tmp))

    def test_backfill_keeps_invalid_quotes_and_original_sampling_time(self):
        window = {'day': '2020-01-02', 'bucket': 'open',
                  'start': self.start.isoformat(),
                  'end': (self.start + timedelta(seconds=1)).isoformat()}
        with tempfile.TemporaryDirectory() as tmp, \
                patch('spreads._load_dotenv'), \
                patch.dict(os.environ, {'APCA_API_KEY_ID': 'test', 'APCA_API_SECRET_KEY': 'test'}), \
                patch('spreads.ThrottledStockClient') as client:
            root = Path(tmp)
            path = root / '2020-01-02-open.json'
            path.write_text(json.dumps({'window': window, 'samples': {
                'SPY': {'status': 'no_update'}, 'AAPL': {'status': 'locked_or_crossed'}}}))
            client.return_value.get_stock_quotes.return_value.data = {'SPY': [self.quote(-10)]}
            fetch_plan({'symbols': ['SPY', 'AAPL'], 'windows': [window]}, root, backfill=True)
            doc = json.loads(path.read_text())
            req = client.return_value.get_stock_quotes.call_args.args[0]
            self.assertEqual(req.symbol_or_symbols, ['SPY'])
            # Alpaca's request model normalizes aware datetimes to naive UTC.
            self.assertEqual(req.end.replace(tzinfo=timezone.utc), self.start + timedelta(seconds=1))
            self.assertEqual(doc['samples']['AAPL']['status'], 'locked_or_crossed')
            self.assertEqual(doc['samples']['SPY']['quote_age_seconds'], 11.)
            fetch_plan({'symbols': ['SPY', 'AAPL'], 'windows': [window]}, root, backfill=True)
            self.assertEqual(client.return_value.get_stock_quotes.call_count, 1)

    def test_partial_backfill_cannot_publish_mixed_method_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'sample-plan'
            root.mkdir()
            window = {'day': '2020-01-02', 'bucket': 'open'}
            (root.parent / 'backfill-plan.json').write_text(json.dumps({'base_plan': root.name}))
            (root / '2020-01-02-open.json').write_text(json.dumps({'window': window}))
            with self.assertRaisesRegex(RuntimeError, 'Incomplete backfill'):
                summarize({'windows': [window]}, root)


if __name__ == '__main__':
    unittest.main()
