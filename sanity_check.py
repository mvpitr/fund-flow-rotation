"""End-to-end sanity checks for the flow panel, plus the current rotation output.

Validates the persisted SQLite panel (data/flows.db) on its own terms and against
independent data (prices), then prints what the latest data implies. Read-only.

Two recurring terms: an "anchor" is a reported quarter-end net-assets value,
taken as ground truth for the asset reconstruction; the AUM identity is
A_t = A_{t-1}(1+r_t) + F_t, assets grow by return plus net new money.

Usage:
    python sanity_check.py
"""

import sqlite3

import numpy as np
import pandas as pd
import yfinance as yf

from categories import category_panel, universe_g, cumulative_flow
from rotation import relative_flow, z_score, momentum

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


def _price_window(months):
    """Price-history window covering the panel's months: one bar before the
    first month (so its pct_change return exists) through the last month
    (yfinance's end is exclusive, so step one month past its bar)."""
    return months.min() - pd.offsets.MonthBegin(2), months.max() + pd.offsets.MonthBegin(1)


def check_returns(panel):
    print("\n" + "=" * 70)
    print("3. RETURN CROSS-CHECK  (N-PORT reported vs price-derived monthly return)")
    print("=" * 70)
    tickers = sorted(panel["ticker"].unique())
    start, end = _price_window(panel["month"])
    px = yf.download(tickers, start=start, end=end,
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
    cur = panel[panel["month"] == latest]
    total_aum = cur["aum"].sum()
    print(f"  latest month: {latest.date()}   total universe AUM: ${total_aum/B:,.1f}B")
    print("  AUM ranking (largest sectors should be Tech / Financials / Health):")
    for _, r in cur.sort_values("aum", ascending=False).head(4).iterrows():
        print(f"    {r['ticker']:5s} {r['category']:24s} ${r['aum']/B:5.1f}B")
    g_U = universe_g(panel).set_index("month")["g_U"].loc[latest]
    print(f"  whole-universe flow g_U: {g_U*100:+.2f}%")


def check_conservation(panel):
    """Zero-sum check: AUM-weighted relative flows cancel exactly, every month.

    Weighting relative flow by prior assets and summing over categories gives
    sum_c A_{c,t-1} rel_{c,t} = 0 identically, so rotation is zero-sum in
    dollars by construction; a violation indicates an aggregation or alignment
    defect in the panel, not a property of the data. Scope: months with no
    mid-history category entries (an entering category's first month leaves a
    residual equal to its own flow); the live panel has none. Raw dollar flow
    does not net to zero: the remainder is the common tide into or out of the
    sector complex that the relative measure removes.

    @math_ref eq:flow_conservation
    """
    print("\n" + "=" * 70)
    print("6. FLOW CONSERVATION  (rotation is zero-sum in dollars)")
    print("=" * 70)
    rel = relative_flow(category_panel(panel), panel).dropna(subset=["rel", "aum_prev"])
    nonfinite = int((~np.isfinite(rel["rel"])).sum())
    print(f"  non-finite rel values: {nonfinite}  [{'OK' if nonfinite == 0 else 'FAIL'}]")
    w = rel.groupby("month").apply(lambda d: (d["aum_prev"] * d["rel"]).sum(),
                                   include_groups=False)
    s = rel.groupby("month").apply(lambda d: (d["aum_prev"] * d["rel"].abs()).sum(),
                                   include_groups=False)
    worst = float((w.abs() / s).max())
    print(f"  months checked: {len(w)}   max |sum_c A_prev*rel|: ${w.abs().max():,.6f}")
    print(f"  max relative to gross: {worst:.1e}  [{'OK' if worst < 1e-10 else 'FAIL'}]")
    tide = panel.groupby("month")["F"].sum()
    gross = panel.groupby("month")["F"].apply(lambda x: x.abs().sum())
    print(f"  raw net flow (not zero-sum, the common tide): mean {tide.mean()/B:+.2f}B/mo, "
          f"median |net|/gross {(tide.abs()/gross).median():.0%}")


def _quadrant(rel, mom):
    """Place a sector by relative flow (strength) and momentum (rising/falling)."""
    if rel >= 0:
        return "leading" if mom >= 0 else "weakening"
    return "improving" if mom >= 0 else "lagging"


def current_output(panel):
    print("\n" + "#" * 70)
    print("# CURRENT OUTPUT: where money is rotating")
    print("#" * 70)

    # Aggregate per-fund flows to category flows + growth, then rotation metrics.
    cat = cumulative_flow(category_panel(panel), window=6)
    rot = momentum(z_score(relative_flow(cat, panel), lookback=12), lag=3)
    g_U = universe_g(panel).set_index("month")["g_U"]
    latest = cat["month"].max()

    cur = cat[cat["month"] == latest].sort_values("F", ascending=False)
    print(f"\nA) Latest month ({latest.date()}) net flow by sector:")
    for _, r in cur.iterrows():
        print(f"   {r['category']:24s} {r['F']/M:>+9,.0f}M   g={r['g']*100:>+6.2f}%")
    print(f"   {'whole-market baseline g_U':24s} {'':>9s}    g={g_U.loc[latest]*100:>+6.2f}%")

    print("\nB) Trailing 6-month cumulative flow (the sustained trend):")
    for _, r in cur.sort_values("CF6", ascending=False).iterrows():
        print(f"   {r['category']:24s} {r['CF6']/B:>+6.2f}B over 6mo")

    print("\nC) Rotation map (rel = g - market g_U; z vs own 12m history; mom = 3m change in rel):")
    cur_rot = rot[rot["month"] == latest].dropna(subset=["rel", "mom"]).sort_values("rel", ascending=False)
    print(f"   {'sector':24s} {'rel%':>7s} {'z':>6s} {'mom%':>7s}   quadrant")
    for _, r in cur_rot.iterrows():
        print(f"   {r['category']:24s} {r['rel']*100:>+6.2f} {r['z']:>+6.2f} "
              f"{r['mom']*100:>+6.2f}   {_quadrant(r['rel'], r['mom'])}")


if __name__ == "__main__":
    panel = load()
    check_completeness(panel)
    check_values(panel)
    check_returns(panel)
    check_aum_identity(panel)
    check_aggregate(panel)
    check_conservation(panel)
    current_output(panel)
