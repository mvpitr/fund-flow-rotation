"""Build a monthly flow panel for a universe of ETFs and persist it.

The universe is the fixed set of funds under study; universe.csv maps each
ticker to its sector and SEC series id. This script pulls reported monthly
flows from SEC N-PORT for every fund in one pass (nport_flows.fetch_many),
normalizes them by fund size via the assets-under-management (AUM) identity,
and stores a tidy panel -- long format, one row per (ticker, month) -- in a
SQLite database (data/flows.db).

The store is keyed on (ticker, month), so re-running upserts (inserts new rows,
updates existing ones in place) as fresh N-PORT filings post -- this is how the
"future data" accrues over time.

Usage:
    EDGAR_IDENTITY="Your Name your@email.com" python build_universe.py
"""

import os
import sqlite3

import pandas as pd

from nport_flows import fetch_many, reconstruct_aum

UNIVERSE_CSV = "universe.csv"
DB_PATH = "data/flows.db"
# Per-fund frame columns (month lives in the index here); DB_COLUMNS adds month.
COLUMNS = ["ticker", "category", "sales", "reinvestment", "redemption",
           "F", "ret_pct", "net_assets", "aum", "g"]
DB_COLUMNS = ["ticker", "month"] + COLUMNS[1:]


def load_universe(path=UNIVERSE_CSV):
    return pd.read_csv(path)


def build_panel(universe):
    """Return a tidy long DataFrame: one row per (ticker, month) with flows + g."""
    series_to_ticker = dict(zip(universe["series_id"], universe["ticker"]))
    cat = dict(zip(universe["ticker"], universe["category"]))
    panels = fetch_many(series_to_ticker)

    frames = []
    for ticker, df in panels.items():
        df = reconstruct_aum(df)
        df["ticker"] = ticker
        df["category"] = cat[ticker]
        frames.append(df[COLUMNS])
    panel = pd.concat(frames).reset_index().rename(columns={"index": "month"})
    panel["month"] = pd.to_datetime(panel["month"]).dt.strftime("%Y-%m-%d")
    return panel.sort_values(["ticker", "month"]).reset_index(drop=True)


def persist(panel, universe, db_path=DB_PATH):
    """Upsert the panel into SQLite keyed on (ticker, month); store the universe too."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    con = sqlite3.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS monthly_flows (
            ticker TEXT, month TEXT, category TEXT,
            sales REAL, reinvestment REAL, redemption REAL,
            F REAL, ret_pct REAL, net_assets REAL, aum REAL, g REAL,
            PRIMARY KEY (ticker, month)
        )""")
    rows = [tuple(None if pd.isna(v) else v for v in r) for r in panel[DB_COLUMNS].itertuples(index=False)]
    con.executemany(
        f"INSERT OR REPLACE INTO monthly_flows ({','.join(DB_COLUMNS)}) "
        f"VALUES ({','.join('?' * len(DB_COLUMNS))})", rows)
    universe.to_sql("universe", con, if_exists="replace", index=False)
    con.commit()
    con.close()


def _summary(panel):
    M = 1e6
    print(f"\nFlow panel: {panel['ticker'].nunique()} ETFs, {len(panel)} rows, "
          f"{panel['month'].min()} -> {panel['month'].max()}")
    latest = panel["month"].max()
    snap = (panel[panel["month"] == latest]
            .assign(F_M=lambda d: d["F"] / M, g_pct=lambda d: d["g"] * 100)
            .sort_values("F_M", ascending=False))
    print(f"\nLatest month ({latest}) net flow by sector:")
    for _, r in snap.iterrows():
        print(f"  {r['ticker']:5s} {r['category']:24s} {r['F_M']:>+9,.0f}M USD   g={r['g_pct']:>+6.2f}%")


if __name__ == "__main__":
    universe = load_universe()
    print(f"Building flow panel for {len(universe)} ETFs from SEC N-PORT...")
    panel = build_panel(universe)
    persist(panel, universe)
    _summary(panel)
    print(f"\nsaved -> {DB_PATH} (tables: monthly_flows, universe)")
