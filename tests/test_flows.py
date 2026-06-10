"""Offline, deterministic unit tests for the core flow math and persistence.

No network: every test builds synthetic inputs so the logic is exercised in
isolation. Run with `pytest` from the repo root.
"""

import sqlite3
from decimal import Decimal
from types import SimpleNamespace as NS

import pandas as pd
import pytest

from shares_flow import compute_flows
from nport_flows import _rows_from_obj, _to_monthly, reconstruct_aum
import build_universe


# --------------------------------------------------------------------------- #
# compute_flows: shares-based daily flow, including the split-neutralization
# --------------------------------------------------------------------------- #
def test_compute_flows_normal_and_split():
    # day1: 100 shares created at price 110 -> +11,000 flow.
    # day2: a 2:1 split doubles shares (1100 -> 2200) with NO real flow.
    df = pd.DataFrame(
        {"price": [100.0, 110.0, 60.0],
         "split": [0.0, 0.0, 2.0],
         "shares": [1000.0, 1100.0, 2200.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
    )
    out = compute_flows(df)

    assert out["F"].iloc[1] == pytest.approx(11000.0)      # real creation
    assert out["F"].iloc[2] == pytest.approx(0.0)          # split -> zero flow
    assert out["g"].iloc[1] == pytest.approx(0.11)         # 11000 / (1000*100)


def test_compute_flows_skips_rows_without_shares():
    df = pd.DataFrame(
        {"price": [100.0, 110.0], "split": [0.0, 0.0], "shares": [float("nan"), 1100.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )
    out = compute_flows(df)
    assert len(out) == 1                                   # leading NaN-shares row dropped


# --------------------------------------------------------------------------- #
# reconstruct_aum: re-anchoring (the dividend-drift regression)
# --------------------------------------------------------------------------- #
def _monthly_df():
    idx = pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"])
    return pd.DataFrame(
        {"net_assets": [1000.0, float("nan"), 1200.0],    # anchors at m0 and m3
         "ret_pct": [0.0, 10.0, -5.0],
         "F": [0.0, 50.0, -20.0]},
        index=idx,
    )


def test_reconstruct_aum_rolls_between_anchors():
    out = reconstruct_aum(_monthly_df())
    # m1 has no reported net_assets: AUM_1 = 1000*(1+0.10) + 50 = 1150
    assert out["aum"].iloc[1] == pytest.approx(1150.0)
    assert out["g"].iloc[1] == pytest.approx(50.0 / 1000.0)


def test_reconstruct_aum_reanchors_exactly_no_drift():
    """Regression: a reported net_assets must be honored exactly, not drifted past.

    A single-anchor roll would give AUM_2 = 1150*(1-0.05) + (-20) = 1072.5, the
    wrong basis for the next quarter. Re-anchoring snaps AUM_2 to the reported 1200.
    """
    out = reconstruct_aum(_monthly_df())
    assert out["aum"].iloc[2] == pytest.approx(1200.0)     # snapped, not 1072.5


# --------------------------------------------------------------------------- #
# _rows_from_obj: month ordering (month3 == reporting month) and F definition
# --------------------------------------------------------------------------- #
def _fake_filing_obj():
    def flow(sales, reinv, redeem):
        return NS(sales=Decimal(sales), reinvestment=Decimal(reinv), redemption=Decimal(redeem))
    ret = NS(return1=Decimal("1.0"), return2=Decimal("2.0"), return3=Decimal("3.0"))
    fi = NS(
        monthly_flow1=flow("100", "0", "40"),
        monthly_flow2=flow("200", "0", "50"),
        monthly_flow3=flow("300", "0", "90"),
        return_info=NS(monthly_total_returns=[ret]),
        net_assets=Decimal("5000"),
    )
    return NS(fund_info=fi, general_info=NS(rep_period_date="2024-03-31"))


def test_rows_from_obj_month_mapping_and_flow():
    rows = _rows_from_obj(_fake_filing_obj())
    months = [r["month"] for r in rows]
    assert months == list(pd.to_datetime(["2024-01-31", "2024-02-29", "2024-03-31"]))
    assert [r["F"] for r in rows] == [60.0, 150.0, 210.0]          # sales - redemption
    assert [r["ret_pct"] for r in rows] == [1.0, 2.0, 3.0]
    # net_assets reported only for month3 (the reporting-period end)
    assert rows[0]["net_assets"] is None and rows[2]["net_assets"] == 5000.0


def test_to_monthly_dedupes_keeping_last():
    rows = [
        {"month": pd.Timestamp("2024-01-31"), "F": 1.0},
        {"month": pd.Timestamp("2024-01-31"), "F": 2.0},   # later record wins
        {"month": pd.Timestamp("2024-02-29"), "F": 3.0},
    ]
    df = _to_monthly(rows)
    assert len(df) == 2
    assert df.loc[pd.Timestamp("2024-01-31"), "F"] == 2.0


# --------------------------------------------------------------------------- #
# persistence: SQLite upsert is idempotent and updates in place
# --------------------------------------------------------------------------- #
def _panel(g_value):
    return pd.DataFrame([
        {"ticker": "XLK", "month": "2024-01-31", "category": "Technology",
         "sales": 1.0, "reinvestment": 0.0, "redemption": 0.0,
         "F": 1.0, "ret_pct": 1.0, "net_assets": 100.0, "aum": 100.0, "g": g_value},
        {"ticker": "XLE", "month": "2024-01-31", "category": "Energy",
         "sales": 2.0, "reinvestment": 0.0, "redemption": 1.0,
         "F": 1.0, "ret_pct": 2.0, "net_assets": 50.0, "aum": 50.0, "g": 0.02},
    ])


def test_persist_upsert_is_idempotent(tmp_path):
    db = str(tmp_path / "flows.db")
    uni = pd.DataFrame([{"ticker": "XLK", "category": "Technology"}])

    build_universe.persist(_panel(0.01), uni, db_path=db)
    build_universe.persist(_panel(0.99), uni, db_path=db)   # same keys, new value

    con = sqlite3.connect(db)
    n = con.execute("SELECT COUNT(*) FROM monthly_flows").fetchone()[0]
    g = con.execute("SELECT g FROM monthly_flows WHERE ticker='XLK'").fetchone()[0]
    con.close()
    assert n == 2                                          # no duplicate rows
    assert g == pytest.approx(0.99)                        # value updated in place
