"""Offline regression checks for cache recovery and HTTP-level rate limiting."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import fetch_intraday as fetch


class FetchTests(unittest.TestCase):
    def test_each_http_page_is_throttled(self):
        with patch.object(fetch.StockHistoricalDataClient, '_one_request', return_value={}), \
                patch.object(fetch.time, 'monotonic', side_effect=[10, 10.1, 10.35]), \
                patch.object(fetch.time, 'sleep') as sleep:
            client = fetch.ThrottledStockClient('test', 'test')
            client._one_request('GET', 'unused', {}, 0)
            client._one_request('GET', 'unused', {}, 0)
            self.assertAlmostEqual(sleep.call_args.args[0], 0.25)

    def test_resume_retries_empty_and_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fetch, 'OUT_DIR', tmp), \
                patch.object(fetch, 'MANIFEST_PATH', os.path.join(tmp, 'manifest.json')):
            manifest = {'SPY': {'2016-01': {'status': 'empty'},
                                '2016-02': {'status': 'ok'}}}
            cutoff = datetime(2016, 3, 2, tzinfo=timezone.utc)

            def response(client, symbol, start, end):
                ts = pd.DatetimeIndex([start + pd.Timedelta(hours=15), end])
                return pd.DataFrame({'timestamp': ts, 'open': 1., 'high': 1.,
                                     'low': 1., 'close': 1., 'volume': 10.})

            with patch.object(fetch, 'fetch_month', side_effect=response) as get:
                fetch.fetch_symbol(None, 'SPY', manifest, cutoff)
                self.assertEqual(get.call_count, 3)
                # Inclusive endpoint must not leak into the next partition.
                self.assertEqual(len(pd.read_parquet(Path(tmp) / 'SPY/2016-01.parquet')), 1)
                fetch.fetch_symbol(None, 'SPY', manifest, cutoff)
                self.assertEqual(get.call_count, 4)  # current month only

    def test_empty_is_saved_and_cannot_overwrite_good_cache(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(fetch, 'OUT_DIR', tmp), \
                patch.object(fetch, 'MANIFEST_PATH', os.path.join(tmp, 'manifest.json')), \
                patch.object(fetch, 'fetch_month', return_value=pd.DataFrame()):
            manifest = {}
            cutoff = datetime(2016, 1, 5, tzinfo=timezone.utc)
            fetch.fetch_symbol(None, 'SPY', manifest, cutoff)
            self.assertEqual(json.loads(Path(fetch.MANIFEST_PATH).read_text())['SPY']['2016-01']['status'], 'empty')
            manifest['SPY']['2016-01']['status'] = 'ok'
            with self.assertRaisesRegex(RuntimeError, 'keeping previous cache'):
                fetch.fetch_symbol(None, 'SPY', manifest, cutoff)


if __name__ == '__main__':
    unittest.main()
