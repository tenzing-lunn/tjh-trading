"""Read-only cache inventory for I1.1. This is not the I1.2 quality gate.

Run python3 audit_intraday.py; vendor-derived tables stay in research_data/.
"""
import json
from pathlib import Path

import duckdb


def main():
    conn = duckdb.connect()
    conn.execute("SET threads=4")
    conn.execute("""CREATE VIEW bars AS SELECT *,
        split_part(filename, '/', -2) AS symbol,
        timezone('America/New_York', timestamp)::DATE AS session_date
        FROM read_parquet('intraday/*/*.parquet', filename=true)""")
    summary = conn.sql("""SELECT symbol, count(*) AS rows,
        count(*) FILTER (WHERE regular) AS regular_rows,
        min(timestamp) AS first, max(timestamp) AS last
        FROM bars GROUP BY symbol ORDER BY symbol""").df()
    sessions = conn.sql("""SELECT symbol, session_date, count(*) AS n,
        count(DISTINCT timestamp) AS distinct_n FROM bars WHERE regular
        GROUP BY symbol, session_date ORDER BY symbol, session_date""").df()
    extremes = conn.sql("""WITH r AS (
        SELECT symbol,session_date,timestamp,close,
        lag(close) OVER w AS prev,lag(timestamp) OVER w AS prev_t
        FROM bars WHERE regular WINDOW w AS
        (PARTITION BY symbol,session_date ORDER BY timestamp))
        SELECT symbol,session_date,timestamp,close/prev-1 AS ret FROM r
        WHERE timestamp-prev_t = INTERVAL '1 minute' AND abs(close/prev-1)>0.2
        ORDER BY symbol,timestamp""").df()
    files = conn.sql("""SELECT filename, count(*) AS rows,
        count(*) FILTER (WHERE regular) AS regular_rows FROM bars GROUP BY filename""").df()
    manifest = json.loads(Path('intraday/manifest.json').read_text())
    expected = {str(Path('intraday') / sym / (month + '.parquet')): rec
                for sym, months in manifest.items() for month, rec in months.items()
                if rec['status'] == 'ok'}
    assert set(files.filename) == set(expected), 'Manifest/file set differs'
    for row in files.itertuples():
        rec = expected[row.filename]
        assert (row.rows, row.regular_rows) == (rec['rows'], rec['regular_rows']), row.filename
    out = Path('research_data/intraday_audit')
    out.mkdir(parents=True, exist_ok=True)
    for name, frame in [('symbols', summary), ('sessions', sessions), ('extreme_returns', extremes)]:
        frame.to_csv(out / (name + '.csv'), index=False)
    print(summary.to_string(index=False))
    print('Rows:', int(summary.rows.sum()), 'regular:', int(summary.regular_rows.sum()))
    print('Median bars/session:', sessions.groupby('symbol').n.median().to_dict())
    print('Sessions <234 bars:', len(sessions[sessions.n < 234]),
          '(includes valid early closes; calendar validation belongs to I1.2)')
    print('Duplicate regular timestamps:', int((sessions.n - sessions.distinct_n).sum()))
    print('Extreme consecutive 1-minute returns:', len(extremes))
    print('Manifest counts match all', len(files), 'parquet files.')


if __name__ == '__main__':
    main()
