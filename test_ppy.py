"""Tests for periods-per-year inference (plan/14 I0.2). Run: python3 test_ppy.py"""
import numpy as np
import pandas as pd

from backtest import run_backtest
from costs import CostModel
from diagnostics import per_year_returns
from metrics import compute_metrics, infer_ppy


def session_index(minutes, days=5, start='2024-01-02'):
    """Regular-session (09:30-16:00) bar timestamps over `days` business days."""
    out = []
    for d in pd.bdate_range(start, periods=days):
        out.extend(pd.date_range(d + pd.Timedelta(hours=9, minutes=30), periods=390 // minutes,
                                 freq=f'{minutes}min'))
    return pd.DatetimeIndex(out)


def expect_raises(index, label):
    try:
        infer_ppy(index)
    except ValueError:
        return
    raise AssertionError(f"{label}: expected ValueError")


def main():
    assert infer_ppy(pd.bdate_range('2020-01-01', periods=500)) == 252
    assert infer_ppy(session_index(1)) == 98_280
    assert infer_ppy(session_index(5)) == 19_656
    assert infer_ppy(session_index(1, start='2024-01-02').tz_localize('America/New_York')) == 98_280
    assert infer_ppy(pd.date_range('2020-01-03', periods=100, freq='W-FRI')) == 52
    assert infer_ppy(pd.date_range('2020-01-31', periods=60, freq='BME')) == 12
    # never guess
    ext = pd.DatetimeIndex([t for d in pd.bdate_range('2024-01-02', periods=3)
                            for t in pd.date_range(d + pd.Timedelta(hours=4), periods=960, freq='1min')])
    expect_raises(ext, 'extended hours')
    expect_raises(pd.RangeIndex(100), 'non-datetime')
    expect_raises(pd.date_range('2020-01-01', periods=50, freq='15D'), 'between buckets')
    rng = np.random.default_rng(0)
    irregular = pd.Timestamp('2024-01-02 09:30') + pd.to_timedelta(
        np.cumsum(rng.integers(1, 30, 300)), unit='s')
    expect_raises(pd.DatetimeIndex(irregular), 'irregular seconds')

    # Sharpe on a synthetic 1-min series == manual formula at ppy = 98,280
    idx = session_index(1, days=10)
    px = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.00002, 0.0005, len(idx)))), index=idx)
    out, m = run_backtest(px, pd.Series(1.0, index=idx), CostModel(0, 0))
    net = out['net'].values
    manual = net.mean() * 98_280 / (net.std(ddof=1) * np.sqrt(98_280))
    assert np.isclose(m['sharpe'], manual, rtol=1e-12), (m['sharpe'], manual)
    assert compute_metrics(out, ppy=252)['sharpe'] != m['sharpe']      # explicit ppy wins

    # per-year split still groups intraday bars by calendar year
    yidx = session_index(5, days=6, start='2023-12-27')
    rows = per_year_returns(pd.Series(0.0001, index=yidx))
    assert [r['period'] for r in rows] == ['2023', '2024'], rows
    assert sum(r['bars'] for r in rows) == len(yidx)
    print("test_ppy: all tests passed")


if __name__ == '__main__':
    main()
