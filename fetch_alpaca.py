"""Pull SPLIT/DIVIDEND-ADJUSTED daily bars from Alpaca into the harness CSV format.
Parallel to fetch_data.py (yfinance), but uses your free Alpaca market-data entitlement.
Run LOCALLY (needs internet + your keys in the environment):

    pip install -r requirements-alpaca.txt
    export APCA_API_KEY_ID=...        # your PAPER key id
    export APCA_API_SECRET_KEY=...    # your PAPER secret
    python fetch_alpaca.py SPY                  # -> spy.csv (8y daily, adjusted)
    python fetch_alpaca.py AAPL 2015-01-01      # -> aapl.csv from a start date
    python run.py spy.csv                        # feed it straight into the harness

Writes columns: open,high,low,close,volume  (dated index) -- exactly what run.py expects.
adjustment='all' folds in splits AND dividends, so there are no fake gaps to trade on.
"""
import os
import sys
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment, DataFeed


def main():
    sym = (sys.argv[1] if len(sys.argv) > 1 else "SPY").upper()
    start = sys.argv[2] if len(sys.argv) > 2 else (
        datetime.utcnow() - timedelta(days=365 * 8)).strftime("%Y-%m-%d")

    key, secret = os.getenv("APCA_API_KEY_ID"), os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        sys.exit("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in your environment first.")

    client = StockHistoricalDataClient(key, secret)
    # Cap end at (now - 16 minutes) to avoid "subscription does not permit querying recent SIP data"
    end = datetime.utcnow() - timedelta(minutes=16)
    req = StockBarsRequest(
        symbol_or_symbols=sym,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.SIP,                  # SIP = all exchanges (vs IEX ~2.5% of volume)
        adjustment=Adjustment.ALL,          # splits + dividends -> no fake jumps
    )
    df = client.get_stock_bars(req).df
    if df.empty:
        sys.exit(f"No bars returned for {sym}. Check the symbol and your data entitlement.")

    # get_stock_bars returns a (symbol, timestamp) multiindex; collapse to a date index.
    df = df.reset_index()
    df["date"] = df["timestamp"].dt.tz_convert(None).dt.normalize()
    out = (df.set_index("date")[["open", "high", "low", "close", "volume"]]
             .sort_index())
    path = f"{sym.lower()}.csv"
    out.to_csv(path)
    print(f"saved {path}  ({len(out)} rows, {out.index.min().date()} -> {out.index.max().date()})")


if __name__ == "__main__":
    main()
