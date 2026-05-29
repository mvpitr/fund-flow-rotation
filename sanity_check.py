"""End-to-end sanity checks for the flow panel, plus the current rotation output.

Validates the persisted SQLite panel (data/flows.db) on its own terms and against
independent data (prices), then prints what the latest data implies. Read-only.

Usage:
    python sanity_check.py
"""

import sqlite3

import pandas as pd
import yfinance as yf

DB_PATH = "data/flows.db"
M = 1e6
B = 1e9


def load():
    con = sqlite3.connect(DB_PATH)
    panel = pd.read_sql("SELECT * FROM monthly_flows", con, parse_dates=["month"])
    con.close()
    return panel.sort_values(["ticker", "month"]).reset_index(drop=True)


def check_completeness(panel):
    print("=" * 70)
    print("1. PANEL COMPLETENESS")
    print("=" * 70)
    print(f"  ETFs: {panel['ticker'].nunique()}   rows: {len(panel)}   "
          f"range: {panel['month'].min().date()} -> {panel['month'].max().date()}")
    dupes = panel.duplicated(["ticker", "month"]).sum()
    print(f"  duplicate (ticker,month) keys: {dupes}  [{'OK' if dupes == 0 else 'FAIL'}]")
    for tk, g in panel.groupby("ticker"):
        full = pd.date_range(g["month"].min(), g["month"].max(), freq="ME")
        gaps = len(set(full.normalize()) - set(g["month"].dt.normalize()))
        flag = "OK" if gaps == 0 else f"{gaps} GAPS"
        print(f"    {tk:5s} {len(g):3d} months  {g['month'].min().date()} -> "
              f"{g['month'].max().date()}  [{flag}]")
    nnull = panel["g"].isna().sum()
    print(f"  rows with null g (pre-anchor months, expected few): {nnull}")


def check_values(panel):
    print("\n" + "=" * 70)
    print("2. VALUE PLAUSIBILITY")
    print("=" * 70)
    bad_id = (~((panel["F"] - (panel["sales"] - panel["redemption"])).abs() < 1.0)).sum()
    print(f"  F == sales - redemption everywhere: {'OK' if bad_id == 0 else f'{bad_id} FAIL'}")
    neg_aum = (panel["net_assets"].dropna() <= 0).sum() + (panel["aum"].dropna() <= 0).sum()
    print(f"  net_assets/aum strictly positive: {'OK' if neg_aum == 0 else f'{neg_aum} FAIL'}")
    g = panel["g"].dropna()
    extreme = (g.abs() > 0.10).sum()
    print(f"  normalized flow g: median {g.median()*100:+.2f}%  "
          f"5th/95th pct {g.quantile(.05)*100:+.2f}% / {g.quantile(.95)*100:+.2f}%")
    print(f"  months with |g| > 10% (flag for inspection): {extreme}")


def check_returns(panel):
    print("\n" + "=" * 70)
    print("3. RETURN CROSS-CHECK  (N-PORT reported vs price-derived monthly return)")
    print("=" * 70)
    tickers = sorted(panel["ticker"].unique())
    px = yf.download(tickers, start="2019-06-01", end="2026-05-01",
                     interval="1mo", auto_adjust=True, progress=False)["Close"]
    # Align on calendar month (Period) -- monthly bars index on month-start, the
    # panel on month-end, so a raw date join would miss everything.
    pmret = (px.pct_change() * 100)
    pmret.index = pd.to_datetime(pmret.index).to_period("M")
    print(f"  {'ETF':5s} {'corr':>6s} {'mean abs err (pp)':>18s}")
    for tk in tickers:
        s = panel[panel["ticker"] == tk].set_index(panel[panel["ticker"] == tk]["month"].dt.to_period("M"))["ret_pct"]
        j = pd.concat([s.rename("nport"), pmret[tk].rename("price")], axis=1).dropna()
        corr = j["nport"].corr(j["price"])
        mae = (j["nport"] - j["price"]).abs().mean()
        print(f"  {tk:5s} {corr:>6.3f} {mae:>18.3f}")


def check_aum_identity(panel):
    print("\n" + "=" * 70)
    print("4. QUARTER-AHEAD CONSISTENCY  (roll identity anchor->next anchor vs reported)")
    print("=" * 70)
    print("  Predict each reported net_assets by rolling F + return from the prior")
    print("  quarter's anchor. Tests flow/return consistency over one quarter.")
    print(f"  {'ETF':5s} {'quarters':>9s} {'median abs err':>16s}")
    for tk, g in panel.groupby("ticker"):
        g = g.sort_values("month").reset_index(drop=True)
        anchors = g.index[g["net_assets"].notna()].tolist()
        errs = []
        for a, b in zip(anchors, anchors[1:]):
            val = g.loc[a, "net_assets"]
            for j in range(a + 1, b + 1):
                val = val * (1 + (g.loc[j, "ret_pct"] or 0) / 100.0) + g.loc[j, "F"]
            errs.append(abs(val - g.loc[b, "net_assets"]) / g.loc[b, "net_assets"])
        med = pd.Series(errs).median() * 100
        print(f"  {tk:5s} {len(errs):>9d} {med:>15.2f}%")


def check_aggregate(panel):
    print("\n" + "=" * 70)
    print("5. AGGREGATE SANITY")
    print("=" * 70)
    latest = panel["month"].max()
    cur = panel[panel["month"] == latest].copy()
    prev_month = sorted(panel["month"].unique())[-2]
    prev = panel[panel["month"] == prev_month].set_index("ticker")["aum"]
    cur["aum_prev"] = cur["ticker"].map(prev)
    total_aum = cur["aum"].sum()
    print(f"  latest month: {latest.date()}   total universe AUM: ${total_aum/B:,.1f}B")
    print("  AUM ranking (largest sectors should be Tech / Financials / Health):")
    for _, r in cur.sort_values("aum", ascending=False).head(4).iterrows():
        print(f"    {r['ticker']:5s} {r['category']:24s} ${r['aum']/B:5.1f}B")
    g_U = cur["F"].sum() / cur["aum_prev"].sum()
    cur["rel"] = cur["g"] - g_U
    weighted = (cur["aum_prev"] * cur["rel"]).sum()
    print(f"  whole-universe flow g_U: {g_U*100:+.2f}%")
    print(f"  AUM-weighted sum of relative flows (should be ~0): {weighted/M:+.4f}M  "
          f"[{'OK' if abs(weighted) < 1.0 else 'check'}]")


def current_output(panel):
    print("\n" + "#" * 70)
    print("# CURRENT OUTPUT: where money is rotating")
    print("#" * 70)
    latest = panel["month"].max()
    cur = panel[panel["month"] == latest].sort_values("F", ascending=False)
    print(f"\nA) Latest month ({latest.date()}) net flow by sector:")
    for _, r in cur.iterrows():
        print(f"   {r['ticker']:5s} {r['category']:24s} {r['F']/M:>+9,.0f}M   g={r['g']*100:>+6.2f}%")

    print("\nB) Trailing 6-month cumulative flow (the sustained trend):")
    last6 = sorted(panel["month"].unique())[-6:]
    cf = (panel[panel["month"].isin(last6)].groupby(["ticker", "category"])["F"].sum()
          .reset_index().sort_values("F", ascending=False))
    for _, r in cf.iterrows():
        print(f"   {r['ticker']:5s} {r['category']:24s} {r['F']/B:>+6.2f}B over 6mo")


if __name__ == "__main__":
    panel = load()
    check_completeness(panel)
    check_values(panel)
    check_returns(panel)
    check_aum_identity(panel)
    check_aggregate(panel)
    current_output(panel)
