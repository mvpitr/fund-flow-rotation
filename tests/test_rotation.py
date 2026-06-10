"""Offline, deterministic unit tests for the Phase 4 rotation statistics.

No network: every test builds a synthetic (ticker, month) panel so the rotation
math is exercised in isolation. Run with `pytest` from the repo root.
"""

import pandas as pd
import pytest

from categories import category_panel
from rotation import relative_flow, z_score


def _panel(rows):
    """rows: list of (ticker, category, month, F, aum) -> tidy long DataFrame."""
    return pd.DataFrame(
        [{"ticker": t, "category": c, "month": m, "F": f, "aum": a}
         for t, c, m, f, a in rows]
    )


# A run of month-ends, long enough to fill a small z-score lookback window.
MONTHS = pd.date_range("2024-01-31", periods=6, freq="ME").strftime("%Y-%m-%d").tolist()
M0, M1 = MONTHS[0], MONTHS[1]


def _cat(rows):
    """rows: list of (category, month, g) -> a category-panel-shaped frame."""
    return pd.DataFrame([{"category": c, "month": m, "g": g} for c, m, g in rows])


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


# --------------------------------------------------------------------------- #
# z-score: standardized against the L months STRICTLY BEFORE t.
# With prior window [2, 1, 0]: mu = 1, sample std = 1, so g=5 -> z = 4.0. Note
# 4.0 exceeds the inclusive-window ceiling (L-1)/sqrt(L) = 1.15 for L=3, which is
# the whole point of excluding the current month.
# --------------------------------------------------------------------------- #
def test_z_score_strictly_prior_known_value():
    cat = _cat([("Technology", m, g)
                for m, g in zip(MONTHS, [2.0, 1.0, 0.0, 5.0, 0.0, 0.0])])
    out = z_score(cat, lookback=3).set_index("month")
    assert pd.isna(out.loc[MONTHS[0], "z"])      # no prior window yet
    assert pd.isna(out.loc[MONTHS[2], "z"])      # only 2 prior months < L=3
    assert out.loc[MONTHS[3], "z"] == pytest.approx(4.0)   # (5 - 1) / 1


def test_z_score_zero_variance_is_nan():
    # Prior window [1, 1, 1] has zero std -> z undefined, not +/- inf.
    cat = _cat([("Technology", m, g)
                for m, g in zip(MONTHS, [1.0, 1.0, 1.0, 5.0, 5.0, 5.0])])
    out = z_score(cat, lookback=3).set_index("month")
    assert pd.isna(out.loc[MONTHS[3], "z"])


def test_z_score_is_per_category_isolated():
    # Energy's flat history must not leak into Technology's z, and vice versa.
    rows = ([("Technology", m, g) for m, g in zip(MONTHS, [2.0, 1.0, 0.0, 5.0, 0.0, 0.0])]
            + [("Energy", m, g) for m, g in zip(MONTHS, [10.0, 10.0, 10.0, 99.0, 10.0, 10.0])])
    out = z_score(_cat(rows), lookback=3)
    tech = out[out["category"] == "Technology"].set_index("month")
    energy = out[out["category"] == "Energy"].set_index("month")
    assert tech.loc[MONTHS[3], "z"] == pytest.approx(4.0)   # uses Tech history only
    assert pd.isna(energy.loc[MONTHS[3], "z"])              # Energy prior var = 0
