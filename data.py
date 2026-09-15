"""Data layer. Real data via fetch_data.py (run locally). Synthetic generator here
so the harness runs anywhere and we can VERIFY it detects real edge when present."""
import numpy as np
import pandas as pd


def synthetic_ohlcv(n=1500, seed=7, kappa=0.0, sigma=0.012, drift=0.0,
                    level=100.0, start='2018-01-01'):
    """Ornstein-Uhlenbeck on log-price:
        log P_t = log P_{t-1} + kappa*(log level - log P_{t-1}) + drift + sigma*eps
    kappa=0  -> random walk: an efficient market with NO edge to find (sanity floor).
    kappa>0  -> price reverts to `level`: a genuine edge the z-score strategy SHOULD catch.
    This is a test fixture, NOT market data."""
    rng = np.random.default_rng(seed)
    logp = np.empty(n); logp[0] = np.log(level); theta = np.log(level)
    for t in range(1, n):
        logp[t] = logp[t-1] + kappa * (theta - logp[t-1]) + drift + rng.normal(0, sigma)
    close = pd.Series(np.exp(logp), index=pd.bdate_range(start=start, periods=n))
    high = close * (1 + np.abs(rng.normal(0, 0.003, n)))
    low  = close * (1 - np.abs(rng.normal(0, 0.003, n)))
    openp = close.shift(1).fillna(close.iloc[0])
    vol = rng.integers(1_000_000, 5_000_000, n)
    return pd.DataFrame({'open':openp,'high':high,'low':low,'close':close,'volume':vol})


def load_csv(path, warn=True):
    """Load an OHLCV CSV and trim leading PRE-IPO PADDING.

    Some vendors back-pad a ticker's history to a fixed start date with flat,
    zero-volume rows (e.g. nio/sofi sit at a constant price with volume=0 for
    months before they actually listed). Those rows are not market data: a
    mean-reversion strategy reads the dead-flat price as a stable mean and
    fabricates an edge. We drop the leading run of zero-volume rows so the
    series begins at the first real trading bar. Only the *leading* block is
    trimmed -- a genuine zero-volume bar later in the series is left alone."""
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    df.columns = [c.lower() for c in df.columns]
    if 'volume' in df.columns:
        traded = (df['volume'] > 0).values
        if traded.any() and not traded[0]:
            first = int(traded.argmax())            # index of first real trading bar
            if warn:
                print(f"[data] {path}: trimmed {first} leading pre-IPO/zero-volume rows "
                      f"({df.index[0].date()} -> {df.index[first].date()})")
            df = df.iloc[first:]
    # Keep admission at the file boundary: every CSV used by scan/xsect/run is
    # checked, including files fetched by the API. Synthetic fixtures never use
    # this path and retain the core's dependency-light behavior.
    from dq import validate_daily
    validate_daily(df)
    return df


def load_intraday(symbol, start=None, end=None, root='intraday'):
    """Load certified minute data as separate sessions; never bridge excluded days."""
    from dq import load_intraday as checked_sessions
    return checked_sessions(symbol, start=start, end=end, root=root)


def quality_report(path):
    """Inspect a raw OHLCV CSV and return a list of data-quality warnings as
    plain dicts (so the web app can surface them honestly). Reads the RAW file,
    not the trimmed one, so it can report what load_csv silently cleaned."""
    raw = pd.read_csv(path, parse_dates=[0], index_col=0)
    raw.columns = [c.lower() for c in raw.columns]
    out = []
    if 'volume' in raw.columns:
        traded = (raw['volume'] > 0).values
        if traded.any() and not traded[0]:
            n = int(traded.argmax())
            out.append({
                'level': 'info', 'code': 'trimmed_preipo', 'rows': n,
                'message': f"Trimmed {n} leading flat/zero-volume pre-IPO rows "
                           f"({raw.index[0].date()} -> {raw.index[n].date()}); they "
                           f"would otherwise fabricate a mean-reversion edge."})
        zeros = int((raw['volume'].iloc[(traded.argmax() if traded.any() else 0):] == 0).sum())
        if zeros:
            out.append({
                'level': 'warn', 'code': 'interior_zero_volume', 'rows': zeros,
                'message': f"{zeros} zero-volume bar(s) inside the traded range "
                           f"(holidays/halts); kept, but treat their returns with care."})
    return out
