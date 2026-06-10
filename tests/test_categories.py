"""Offline, deterministic unit tests for the Phase 3 category aggregation.

No network: every test builds a synthetic (ticker, month) panel so the aggregation
math is exercised in isolation, including the many-funds-per-category case that the
live 1-fund-per-sector universe does not yet reach. Run with `pytest` from the root.
"""

import pandas as pd
import pytest

from categories import category_panel, universe_g, cumulative_flow


def _panel(rows):
    """rows: list of (ticker, category, month, F, aum) -> tidy long DataFrame."""
    return pd.DataFrame(
        [{"ticker": t, "category": c, "month": m, "F": f, "aum": a}
         for t, c, m, f, a in rows]
    )


M0, M1, M2, M3 = "2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30"


# --------------------------------------------------------------------------- #
# Identity: with one fund per category, category g == that fund's own g.
# --------------------------------------------------------------------------- #
def test_single_fund_category_reduces_to_identity():
    panel = _panel([
        ("XLK", "Technology", M0, 10.0, 100.0),
        ("XLK", "Technology", M1, 20.0, 130.0),
    ])
    cat = category_panel(panel).set_index("month")
    assert cat.loc[M1, "F"] == pytest.approx(20.0)
    assert cat.loc[M1, "aum_prev"] == pytest.approx(100.0)
    assert cat.loc[M1, "g"] == pytest.approx(20.0 / 100.0)   # == the fund's own g
    assert pd.isna(cat.loc[M0, "g"])                          # no prior month


# --------------------------------------------------------------------------- #
# Many funds: category g is the asset-weighted average of member g, NOT the
# simple mean. Two funds with equal flow but different size must weight by size.
# --------------------------------------------------------------------------- #
def test_two_fund_category_is_asset_weighted():
    panel = _panel([
        ("VGT", "Technology", M0, 0.0, 100.0),    # small fund, prior assets 100
        ("XLK", "Technology", M0, 0.0, 300.0),    # large fund, prior assets 300
        ("VGT", "Technology", M1, 20.0, 120.0),   # g = 20/100 = 0.200
        ("XLK", "Technology", M1, 20.0, 320.0),   # g = 20/300 = 0.0667
    ])
    cat = category_panel(panel).set_index("month")
    assert cat.loc[M1, "F"] == pytest.approx(40.0)           # summed dollar flow
    assert cat.loc[M1, "aum_prev"] == pytest.approx(400.0)   # summed prior assets
    # asset-weighted: (100*0.20 + 300*0.0667)/400 = 0.10, not the simple mean 0.133
    assert cat.loc[M1, "g"] == pytest.approx(40.0 / 400.0)
    assert cat.loc[M1, "g"] != pytest.approx((0.20 + 20.0 / 300.0) / 2)


# --------------------------------------------------------------------------- #
# Universe baseline: total flow over total prior assets across every fund.
# --------------------------------------------------------------------------- #
def test_universe_g_is_total_flow_over_total_prior_assets():
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 200.0),
        ("XLE", "Energy",     M0, 0.0, 800.0),
        ("XLK", "Technology", M1, 30.0, 230.0),
        ("XLE", "Energy",     M1, 70.0, 850.0),
    ])
    u = universe_g(panel).set_index("month")
    # g_U = (30+70) / (200+800) = 0.10
    assert u.loc[M1, "g_U"] == pytest.approx(100.0 / 1000.0)
    assert pd.isna(u.loc[M0, "g_U"])


# --------------------------------------------------------------------------- #
# Trailing window: CF(W) is the sum of the last W monthly flows, NaN until full.
# --------------------------------------------------------------------------- #
def test_cumulative_flow_trailing_window():
    panel = _panel([
        ("XLK", "Technology", m, f, 100.0)
        for m, f in zip([M0, M1, M2, M3], [1.0, 2.0, 3.0, 4.0])
    ])
    cat = cumulative_flow(category_panel(panel), window=3).set_index("month")
    assert pd.isna(cat.loc[M0, "CF3"]) and pd.isna(cat.loc[M1, "CF3"])
    assert cat.loc[M2, "CF3"] == pytest.approx(1.0 + 2.0 + 3.0)   # first full window
    assert cat.loc[M3, "CF3"] == pytest.approx(2.0 + 3.0 + 4.0)   # rolls forward


# --------------------------------------------------------------------------- #
# Fund entry: a fund joining mid-history adds its flow to the numerator, but its
# absent prior assets are not in the denominator that month (documented behavior).
# --------------------------------------------------------------------------- #
def test_fund_entering_midhistory_uses_present_funds_only():
    panel = _panel([
        ("XLK", "Technology", M0, 5.0, 100.0),    # only XLK exists at M0
        ("XLK", "Technology", M1, 10.0, 110.0),
        ("VGT", "Technology", M1, 50.0, 50.0),     # VGT enters at M1
    ])
    cat = category_panel(panel).set_index("month")
    assert cat.loc[M1, "F"] == pytest.approx(60.0)           # both funds' flow
    assert cat.loc[M1, "aum_prev"] == pytest.approx(100.0)   # only XLK was present at M0
    assert cat.loc[M1, "g"] == pytest.approx(60.0 / 100.0)


# --------------------------------------------------------------------------- #
# Regression: a month where every member fund's AUM is unknown (NaN) must stay
# NaN at the category level, not collapse to a fabricated zero -- a zero prior
# AUM turns the next month's growth rate into +/-inf. Surfaced by the zero-sum
# sanity check on the live panel (first two pre-anchoring months, 2019-07/08).
# --------------------------------------------------------------------------- #
def test_all_nan_aum_month_stays_nan_no_inf():
    import numpy as np

    panel = _panel([
        ("XLK", "Technology", M0, 5.0, np.nan),   # AUM unknown at M0
        ("XLK", "Technology", M1, 10.0, 100.0),
        ("XLK", "Technology", M2, 4.0, 110.0),
    ])
    cat = category_panel(panel).set_index("month")
    assert pd.isna(cat.loc[M0, "aum"])                        # unknown, not 0.0
    assert pd.isna(cat.loc[M1, "g"])                          # F/NaN, not F/0 = inf
    assert not np.isinf(cat["g"].dropna()).any()
    uni = universe_g(panel).set_index("month")
    assert not np.isinf(uni["g_U"].dropna()).any()
