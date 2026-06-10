"""Offline, deterministic unit tests for the Phase 4 rotation statistics.

No network: every test builds a synthetic (ticker, month) panel so the rotation
math is exercised in isolation. Run with `pytest` from the repo root.
"""

import pandas as pd
import pytest

from categories import category_panel
from rotation import relative_flow


def _panel(rows):
    """rows: list of (ticker, category, month, F, aum) -> tidy long DataFrame."""
    return pd.DataFrame(
        [{"ticker": t, "category": c, "month": m, "F": f, "aum": a}
         for t, c, m, f, a in rows]
    )


M0, M1 = "2024-01-31", "2024-02-29"


# --------------------------------------------------------------------------- #
# relative flow: rel == g_c - g_U on known inputs.
# --------------------------------------------------------------------------- #
def test_relative_flow_subtracts_universe_baseline():
    # Universe: total F at M1 = 30+70 = 100, total prior assets = 200+800 = 1000,
    # so g_U = 0.10. Technology g = 30/200 = 0.15 -> rel = +0.05; Energy g =
    # 70/800 = 0.0875 -> rel = -0.0125.
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 200.0),
        ("XLE", "Energy",     M0, 0.0, 800.0),
        ("XLK", "Technology", M1, 30.0, 230.0),
        ("XLE", "Energy",     M1, 70.0, 850.0),
    ])
    cat = relative_flow(category_panel(panel), panel)
    r = cat[cat["month"] == M1].set_index("category")["rel"]
    assert r["Technology"] == pytest.approx(0.15 - 0.10)
    assert r["Energy"] == pytest.approx(0.0875 - 0.10)


# --------------------------------------------------------------------------- #
# zero-sum: AUM-weighted relative flows sum to ~0 (a pure reallocation).
# Follows from g_U being the asset-weighted mean of the category g's.
# --------------------------------------------------------------------------- #
def test_relative_flows_are_zero_sum_when_asset_weighted():
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 200.0),
        ("XLE", "Energy",     M0, 0.0, 800.0),
        ("XLK", "Technology", M1, 30.0, 230.0),
        ("XLE", "Energy",     M1, 70.0, 850.0),
    ])
    cat = relative_flow(category_panel(panel), panel)
    m1 = cat[cat["month"] == M1]
    weighted = (m1["aum_prev"] * m1["rel"]).sum()
    assert weighted == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# first month has no prior assets, so g and rel are NaN, not spurious zeros.
# --------------------------------------------------------------------------- #
def test_relative_flow_first_month_is_nan():
    panel = _panel([
        ("XLK", "Technology", M0, 5.0, 200.0),
        ("XLK", "Technology", M1, 30.0, 230.0),
    ])
    cat = relative_flow(category_panel(panel), panel).set_index("month")
    assert pd.isna(cat.loc[M0, "rel"])
