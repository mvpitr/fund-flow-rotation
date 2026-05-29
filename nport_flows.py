"""Backfill monthly fund flows from SEC Form N-PORT (free, authoritative).

Yahoo/FMP free tiers give no historical ETF shares series (methodology 7), but
every ETF files Form N-PORT, which reports — for each of the 3 months in the
period — share sales/redemptions (Item B.8), total return (B.7) and net assets
(B.1). So we read *reported* monthly flows directly rather than estimating them
from shares (methodology 2e). Monthly granularity, ~2-month reporting lag.

Usage:
    EDGAR requires an identity. Set EDGAR_IDENTITY="Name email" in the env, then:
        python nport_flows.py            # defaults to XLK
"""

import os
import re

import pandas as pd
import yfinance as yf
from edgar import Company, set_identity
from edgar.funds import find_fund

TICKER = "XLK"
SERIES_RE = re.compile(r"S\d{9}")


def _identity():
    ident = os.environ.get("EDGAR_IDENTITY")
    if not ident:
        raise RuntimeError("Set EDGAR_IDENTITY='Your Name your@email' (SEC requires it).")
    set_identity(ident)


def _series_id(ticker):
    """Resolve an ETF ticker to its SEC series id (e.g. XLK -> S000006415)."""
    return find_fund(ticker).series.series_id


def fetch_nport_flows(ticker=TICKER):
    """Return a monthly DataFrame of reported flows/returns/net-assets for `ticker`."""
    _identity()
    series_id = _series_id(ticker)
    # The trust files one N-PORT per series each quarter; filter to our series
    # cheaply via the SGML header before parsing the (large) holdings XML.
    filings = Company(ticker).get_filings(form="NPORT-P")
    rows = []
    for f in filings:
        if (SERIES_RE.search(str(f.header)) or [None])[0] == series_id:
            rows.extend(_rows_from_obj(f.obj()))
    return _to_monthly(rows)


def _rows_from_obj(obj):
    """Extract three monthly flow/return/net-asset rows from one parsed N-PORT filing."""
    fi = obj.fund_info
    rep = pd.Timestamp(obj.general_info.rep_period_date)
    rets = fi.return_info.monthly_total_returns
    ret = rets[0] if rets else None
    # month3 == reporting month; month1/2 are the two months before it.
    flows = [fi.monthly_flow1, fi.monthly_flow2, fi.monthly_flow3]
    rvals = [getattr(ret, f"return{i}", None) for i in (1, 2, 3)]
    rows = []
    for offset, (mf, rv) in enumerate(zip(flows, rvals)):
        month_end = (rep - pd.offsets.MonthEnd(2 - offset)).normalize()
        sales, reinv, redeem = float(mf.sales), float(mf.reinvestment), float(mf.redemption)
        rows.append({
            "month": month_end,
            "sales": sales,
            "reinvestment": reinv,
            "redemption": redeem,
            "F": sales - redeem,                           # net creation/redemption ($)
            "ret_pct": float(rv) if rv is not None else None,
            # net assets are reported only for the period (month3) end:
            "net_assets": float(fi.net_assets) if offset == 2 else None,
        })
    return rows


def _to_monthly(rows):
    """Rows -> month-indexed frame, de-duping overlapping filings (keep most recent)."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("month").drop_duplicates("month", keep="last").set_index("month")


def fetch_many(series_to_ticker, anchor_ticker="XLK"):
    """Pull the trust's N-PORT filings ONCE and bucket monthly rows by ticker.

    All Select Sector SPDRs live in one trust, so a single pass over its filings
    (filtering each by its SGML-header series id) covers the whole universe far
    more cheaply than scraping per ticker. Returns {ticker: monthly DataFrame}."""
    _identity()
    filings = Company(anchor_ticker).get_filings(form="NPORT-P")
    buckets = {tk: [] for tk in series_to_ticker.values()}
    for f in filings:
        sid = (SERIES_RE.search(str(f.header)) or [None])[0]
        tk = series_to_ticker.get(sid)
        if tk is not None:
            buckets[tk].extend(_rows_from_obj(f.obj()))
    return {tk: _to_monthly(rows) for tk, rows in buckets.items() if rows}


def reconstruct_aum(df):
    """Roll a continuous monthly AUM via the identity AUM_t = AUM_{t-1}(1+r_t)+F_t,
    anchored on the first reported net_assets (methodology 2a), then g_t=F_t/AUM_{t-1}.
    Net assets are reported only at quarter-ends, so rolling the identity forward
    fills the gaps — and re-hitting the later anchors is a built-in accuracy check."""
    df = df.copy()
    anchor = df["net_assets"].first_valid_index()
    if anchor is None:
        df["aum"] = df["g"] = pd.NA
        return df
    aum, prev = {}, None
    for dt, row in df.loc[anchor:].iterrows():
        r = (row["ret_pct"] or 0) / 100.0
        aum[dt] = df.loc[anchor, "net_assets"] if prev is None else aum[prev] * (1 + r) + row["F"]
        prev = dt
    df["aum"] = pd.Series(aum)
    df["aum_prev"] = df["aum"].shift(1)
    df["g"] = df["F"] / df["aum_prev"]
    return df


def _report(ticker=TICKER):
    df = fetch_nport_flows(ticker)
    if df.empty:
        print(f"No N-PORT flows found for {ticker}.")
        return
    df = reconstruct_aum(df)
    M = 1e6
    print(f"\nN-PORT MONTHLY FLOWS — {ticker}  (reported sales/redemptions, Item B.8)")
    print(f"  months         : {len(df)}  ({df.index.min().date()} -> {df.index.max().date()})")
    print(f"  net flow total : {df['F'].sum() / M:,.0f}M USD")
    print(f"  latest net asset: {df['net_assets'].dropna().iloc[-1] / M:,.0f}M USD")

    # Cross-check N-PORT's reported total return against price-based returns.
    px = yf.Ticker(ticker).history(period="6mo", auto_adjust=True)["Close"]
    mret = px.resample("ME").last().pct_change() * 100
    mret.index = mret.index.tz_localize(None).normalize()
    chk = df.join(mret.rename("price_ret_pct"))[["ret_pct", "price_ret_pct"]].dropna().tail(4)
    print("\n  RETURN SANITY CHECK (N-PORT vs price, %):")
    print(chk.to_string(float_format=lambda x: f"{x:,.2f}"))

    # Reconstructed AUM should re-hit the reported net_assets anchors; show the gap.
    anchors = df.dropna(subset=["net_assets"])
    err = ((anchors["aum"] - anchors["net_assets"]) / anchors["net_assets"]).abs()
    print(f"\n  AUM RECONSTRUCTION vs reported net_assets: median abs error "
          f"{err.median() * 100:.2f}% over {len(anchors)} anchors")

    show = df[["F", "aum", "ret_pct", "g"]].tail(12).copy()
    show["F"] = show["F"] / M
    show["aum"] = show["aum"] / M
    show["g"] = show["g"] * 100
    print("\n  LAST 12 MONTHS:")
    print(show.to_string(
        float_format=lambda x: f"{x:,.2f}",
        header=["F ($M)", "AUM* ($M)", "ret %", "g %"],
        na_rep="—",
    ))

    out = f"data/{ticker.lower()}_nport_flows.csv"
    os.makedirs("data", exist_ok=True)
    df.to_csv(out)
    print(f"\n  saved -> {out}")


if __name__ == "__main__":
    _report()
