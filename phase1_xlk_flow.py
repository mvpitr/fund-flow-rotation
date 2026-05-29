"""Phase 1: reconstruct daily fund flows for a single ETF (XLK).

Self-contained on purpose; will be refactored into modules in Phase 2.
Methodology: see docs/methodology.md (sections referenced inline).
"""

from datetime import date, timedelta

import pandas as pd
import yfinance as yf

TICKER = "XLK"
END = date.today()
START = END - timedelta(days=365)


def _naive_dates(idx):
    """Strip timezone and time-of-day so we can align on calendar dates."""
    idx = pd.to_datetime(idx)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def fetch_prices(ticker, start, end):
    # auto_adjust=False -> 'Close' is the RAW price actually seen on day t.
    # We must not use back-adjusted prices to value flows (methodology 2d).
    h = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    out = pd.DataFrame({"price": h["Close"], "split": h["Stock Splits"]})
    out.index = _naive_dates(out.index)
    return out


def fetch_shares(ticker, start, end):
    s = yf.Ticker(ticker).get_shares_full(start=start, end=end)
    if s is None or len(s) == 0:
        return pd.Series(dtype="float64", name="shares")
    s.index = _naive_dates(s.index)
    # Yahoo can emit multiple rows per day; keep the day's last reported value.
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.name = "shares"
    return s


def build_dataset(ticker, start, end):
    prices = fetch_prices(ticker, start, end)
    shares = fetch_shares(ticker, start, end)
    df = prices.copy()
    # Shares are reported irregularly; carry the last known value forward.
    df["shares"] = shares.reindex(df.index).ffill()
    return df


def _diagnostics():
    print(f"Range requested: {START} -> {END}  ({TICKER})\n")

    prices = fetch_prices(TICKER, START, END)
    print("PRICES")
    print(f"  rows         : {len(prices)}")
    print(f"  date range   : {prices.index.min().date()} -> {prices.index.max().date()}")
    print(f"  price NaNs   : {int(prices['price'].isna().sum())}")
    splits = prices.loc[prices['split'] != 0, 'split']
    print(f"  splits (!=0) : {len(splits)}"
          + (f"  -> {dict(zip(splits.index.date.astype(str), splits.values))}" if len(splits) else ""))

    shares_raw = yf.Ticker(TICKER).get_shares_full(start=START, end=END)
    shares = fetch_shares(TICKER, START, END)
    print("\nSHARES OUTSTANDING (get_shares_full)")
    print(f"  raw rows     : {0 if shares_raw is None else len(shares_raw)}")
    print(f"  deduped rows : {len(shares)}")
    if len(shares):
        print(f"  date range   : {shares.index.min().date()} -> {shares.index.max().date()}")
        print(f"  distinct vals: {shares.nunique()}  (how many times the count actually changed)")
        print(f"  min / max    : {shares.min():,.0f} / {shares.max():,.0f}")

    df = build_dataset(TICKER, START, END)
    print("\nMERGED DATASET")
    print(f"  rows            : {len(df)}")
    print(f"  price NaNs      : {int(df['price'].isna().sum())}")
    print(f"  shares NaNs     : {int(df['shares'].isna().sum())}  (leading days before first shares report)")
    print(f"  usable rows     : {int(df[['price','shares']].notna().all(axis=1).sum())}")
    print("\n  HEAD:")
    print(df.head(8).to_string())
    print("\n  TAIL:")
    print(df.tail(8).to_string())


if __name__ == "__main__":
    _diagnostics()
