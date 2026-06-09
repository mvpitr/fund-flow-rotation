"""Phase 1: reconstruct daily fund flows for a single ETF (XLK).

Self-contained on purpose; will be refactored into modules in Phase 2.
Methodology: see docs/fund-flow-rotation.tex (equation labels referenced inline).
"""

import json
import os
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

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
    # We must not use back-adjusted prices to value flows (paper, eq:flow_shares).
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


def fetch_shares_fmp(ticker, start, end):
    """Shares outstanding from Financial Modeling Prep (set FMP_API_KEY in env).

    Yahoo serves no shares-outstanding series for ETFs (paper, sec. Reading the flow); FMP's
    /stable/shares-float DOES cover ETFs. Caveat: on the FREE tier this returns
    only the CURRENT snapshot (one row) — the historical endpoints are premium.
    So this enables a snapshot-forward series, not a backfill. Returns empty if
    no key is set or the request fails (so callers fall back / degrade).
    """
    key = os.environ.get("FMP_API_KEY")
    if not key:
        return pd.Series(dtype="float64", name="shares")
    url = ("https://financialmodelingprep.com/stable/shares-float"
           f"?symbol={ticker}&apikey={key}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
    except urllib.error.HTTPError as e:
        print(f"  [FMP] HTTP {e.code} for {ticker}: {e.read().decode()[:160]}")
        return pd.Series(dtype="float64", name="shares")
    if isinstance(data, dict):  # FMP returns a dict only on error
        print(f"  [FMP] error for {ticker}: {data}")
        return pd.Series(dtype="float64", name="shares")
    recs = {r["date"]: r.get("outstandingShares") for r in data if r.get("outstandingShares")}
    if not recs:
        return pd.Series(dtype="float64", name="shares")
    s = pd.Series(recs, name="shares")
    s.index = _naive_dates(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]


def build_dataset(ticker, start, end):
    prices = fetch_prices(ticker, start, end)
    # Prefer FMP if a key is set (Yahoo has no ETF shares series); else Yahoo.
    shares = fetch_shares_fmp(ticker, start, end)
    if shares.empty:
        shares = fetch_shares(ticker, start, end)
    df = prices.copy()
    # Shares are reported irregularly; carry the last known value forward.
    df["shares"] = shares.reindex(df.index).ffill()
    return df


def compute_flows(df):
    """Add estimated daily flows to the merged dataset.

    @math_ref eq:flow_split
    @math_ref eq:normalized_flow

    F_t = (S_t - k_t * S_{t-1}) * NAV_t      g_t = F_t / (S_{t-1} * NAV_{t-1})

    NAV is proxied by the raw market Close (free data has no NAV feed); ETFs
    trade close to NAV, so this is a small, documented approximation.
    k_t is the split factor (1.0 on normal days, 2.0 for a 2:1, 0.5 for a 1:2),
    which strips the mechanical share-count jump so a pure split shows zero flow.
    """
    out = df.copy()
    # Only consecutive days with both price and shares yield a valid flow.
    usable = out[["price", "shares"]].notna().all(axis=1)
    out = out[usable].copy()

    k = out["split"].where(out["split"] != 0, 1.0)   # split factor, 1.0 if none
    s_prev = out["shares"].shift(1)
    nav_prev = out["price"].shift(1)

    out["aum"] = out["shares"] * out["price"]                 # AUM_t  = S_t * NAV_t
    out["aum_prev"] = s_prev * nav_prev                       # AUM_{t-1}
    flow_shares = out["shares"] - k * s_prev                  # shares created/redeemed, ex-split
    out["F"] = flow_shares * out["price"]                     # dollar flow F_t
    out["g"] = out["F"] / out["aum_prev"]                     # normalized flow g_t
    return out


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


def _flow_report():
    df = build_dataset(TICKER, START, END)
    flows = compute_flows(df)
    valued = flows.dropna(subset=["F", "g"])

    M = 1e6
    print("\n" + "=" * 60)
    print(f"FLOWS  ({TICKER})  — F_t = (S_t - k_t*S_{{t-1}}) * NAV_t")
    print("  NAV proxied by market Close; flows valued in USD.")
    print("=" * 60)

    if valued.empty:
        print("  NO USABLE ROWS — need a shares-outstanding time series.")
        print("  Yahoo's get_shares_full() returns data for stocks but is")
        print("  EMPTY for ETFs, so daily ΔS (and thus flow) can't be formed.")
        print("  Next step: source ETF shares from the issuer or another feed.")
        return
    print(f"  flow days        : {len(valued)}")
    print(f"  days w/ ΔS != 0  : {int((valued['F'] != 0).sum())}  (shares actually changed)")
    print(f"  net flow (period): {valued['F'].sum() / M:,.1f}M USD")
    print(f"  cumulative g     : {valued['g'].sum() * 100:,.2f}%  (sum of daily organic growth)")
    print(f"  latest AUM       : {valued['aum'].iloc[-1] / M:,.0f}M USD")

    moves = valued.loc[valued["F"] != 0]
    if len(moves):
        top = moves["F"].abs().nlargest(5).index
        biggest = moves.loc[top, ["F", "g"]].sort_values("F", ascending=False)
        print("\n  LARGEST FLOW DAYS (signed):")
        for d, row in biggest.iterrows():
            print(f"    {d.date()}   {row['F'] / M:>+10,.1f}M USD   g = {row['g'] * 100:>+6.2f}%")

    print("\n  TAIL (last 8 flow days):")
    show = valued[["price", "shares", "F", "g"]].tail(8).copy()
    show["F"] = show["F"] / M
    show["g"] = show["g"] * 100
    print(show.to_string(
        float_format=lambda x: f"{x:,.2f}",
        header=["price", "shares", "F ($M)", "g (%)"],
    ))

    # Persist for sanity-checking against a known source (data/ is gitignored).
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{TICKER.lower()}_flows.csv"
    valued[["price", "split", "shares", "aum", "F", "g"]].to_csv(out_path)
    print(f"\n  saved -> {out_path}")


if __name__ == "__main__":
    _diagnostics()
    _flow_report()
