"""Offline, deterministic unit tests for the Phase 4 rotation statistics.

No network: every test builds a synthetic (ticker, month) panel so the rotation
math is exercised in isolation. Run with `pytest` from the repo root.
"""

import numpy as np
import pandas as pd
import pytest

from categories import category_panel
from rotation import relative_flow, z_score, momentum, rrg_coordinates, rotation_turnover


def _panel(rows):
    """rows: list of (ticker, category, month, F, aum) -> tidy long DataFrame."""
    return pd.DataFrame(
        [{"ticker": t, "category": c, "month": m, "F": f, "aum": a}
         for t, c, m, f, a in rows]
    )


def _multi_month_panel(n=18):
    """Two sectors over n months with deterministic, varying flows (for windows)."""
    months = pd.date_range("2023-01-31", periods=n, freq="ME").strftime("%Y-%m-%d")
    rows = []
    for base, (tk, cat) in enumerate([("XLK", "Technology"), ("XLE", "Energy")], start=1):
        for i, m in enumerate(months):
            rows.append((tk, cat, m, 100.0 * np.sin(i / 2.0 + base) + 20.0 * base, 1000.0))
    return _panel(rows)


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


# --------------------------------------------------------------------------- #
# momentum: m_{c,t} = rel_{c,t} - rel_{c,t-lag}, the change in relative flow.
# --------------------------------------------------------------------------- #
def _cat_rel(rows):
    """rows: list of (category, month, rel) -> a frame carrying the 'rel' column."""
    return pd.DataFrame([{"category": c, "month": m, "rel": r} for c, m, r in rows])


def test_momentum_differences_relative_flow():
    rel = [0.01, 0.02, 0.03, 0.05, 0.04, 0.06]
    out = momentum(_cat_rel(list(zip(["Tech"] * 6, MONTHS, rel))), lag=3).set_index("month")
    assert pd.isna(out.loc[MONTHS[2], "mom"])                       # < lag prior months
    assert out.loc[MONTHS[3], "mom"] == pytest.approx(0.05 - 0.01)  # rel_t - rel_{t-3}
    assert out.loc[MONTHS[5], "mom"] == pytest.approx(0.06 - 0.03)


def test_momentum_is_per_category_isolated():
    rows = (list(zip(["Tech"] * 6, MONTHS, [0.0, 0.0, 0.0, 0.4, 0.0, 0.0]))
            + list(zip(["Energy"] * 6, MONTHS, [9.0, 9.0, 9.0, 9.0, 9.0, 9.0])))
    out = momentum(_cat_rel(rows), lag=3)
    tech = out[out["category"] == "Tech"].set_index("month")
    energy = out[out["category"] == "Energy"].set_index("month")
    assert tech.loc[MONTHS[3], "mom"] == pytest.approx(0.4)   # 0.4 - 0.0, Tech only
    assert energy.loc[MONTHS[3], "mom"] == pytest.approx(0.0)  # flat -> no momentum


def test_momentum_requires_rel_column():
    cat = _cat([("Tech", m, g) for m, g in zip(MONTHS, range(6))])  # has g, not rel
    with pytest.raises(ValueError, match="rel"):
        momentum(cat, lag=3)


# --------------------------------------------------------------------------- #
# Generalized operators: z_score / momentum on an arbitrary source column.
# These are what build the rotation-graph coordinates from relative flow.
# --------------------------------------------------------------------------- #
def test_z_score_standardizes_named_column():
    # Same numbers as the g test, but on a 'rel' column written out to 'rs'.
    cat = _cat_rel([("Technology", m, r)
                    for m, r in zip(MONTHS, [2.0, 1.0, 0.0, 5.0, 0.0, 0.0])])
    out = z_score(cat, col="rel", lookback=3, out="rs").set_index("month")
    assert out.loc[MONTHS[3], "rs"] == pytest.approx(4.0)   # (5 - 1) / 1
    assert pd.isna(out.loc[MONTHS[2], "rs"])
    assert "z" not in out.columns                            # only the named output


def test_momentum_differences_named_column():
    rs = [0.0, 0.0, 1.0, 4.0, 2.0, 6.0]
    cat = pd.DataFrame([{"category": "Tech", "month": m, "rs": v}
                        for m, v in zip(MONTHS, rs)])
    out = momentum(cat, col="rs", lag=2, out="rs_mom").set_index("month")
    assert out.loc[MONTHS[3], "rs_mom"] == pytest.approx(4.0 - 0.0)   # rs[3] - rs[1]
    assert out.loc[MONTHS[5], "rs_mom"] == pytest.approx(6.0 - 4.0)   # rs[5] - rs[3]


# --------------------------------------------------------------------------- #
# rrg_coordinates wires standardize(rel) -> 'rs' -> momentum -> 'rs_mom'.
# --------------------------------------------------------------------------- #
def test_rrg_coordinates_produces_rs_and_its_momentum():
    # Two sectors with flows that swing relative flow, so rs has real variance.
    flows = {"Technology": [0.0, 10.0, 2.0, 8.0, 3.0],
             "Energy":     [0.0, 2.0, 10.0, 3.0, 8.0]}
    rows = [(("XLK" if c == "Technology" else "XLE"), c, m, f, 100.0)
            for c, fs in flows.items() for m, f in zip(MONTHS[:5], fs)]
    panel = _panel(rows)
    out = rrg_coordinates(category_panel(panel), panel, smooth=1, lookback=2, lag=1)
    assert {"rs", "rs_mom"}.issubset(out.columns)
    assert out["rs"].notna().any()                          # not degenerate
    # rs_mom must be exactly the per-category lag-1 difference of rs.
    expected = out.groupby("category")["rs"].diff(1)
    pd.testing.assert_series_equal(out["rs_mom"], expected, check_names=False)


def test_rrg_smooth_one_matches_unsmoothed():
    """Regression: smooth=1 reproduces standardizing raw relative flow exactly."""
    panel = _multi_month_panel(18)
    out = rrg_coordinates(category_panel(panel), panel, smooth=1, lookback=6, lag=3)
    ref = momentum(z_score(relative_flow(category_panel(panel), panel),
                           col="rel", lookback=6, out="rs"), col="rs", lag=3, out="rs_mom")
    for c in ("rs", "rs_mom"):
        pd.testing.assert_series_equal(out.reset_index(drop=True)[c],
                                       ref.reset_index(drop=True)[c], check_names=False)


def test_rrg_smoothing_is_trailing_mean():
    """rel_bar must be the per-category trailing w-month mean of relative flow."""
    out = rrg_coordinates(category_panel(_multi_month_panel(18)), _multi_month_panel(18),
                          smooth=2, lookback=6, lag=3)
    expected = out.groupby("category")["rel"].transform(
        lambda s: s.rolling(2, min_periods=2).mean())
    pd.testing.assert_series_equal(out["rel_bar"], expected, check_names=False)


# --------------------------------------------------------------------------- #
# Conservation (eq:flow_conservation): AUM-weighted relative flows sum to zero
# in every month with no category entry. At a category's first month its growth
# is undefined, it leaves the sum, and the residual is exactly its own flow --
# the identity's scope condition, asserted as such.
# --------------------------------------------------------------------------- #
def test_relative_flow_is_zero_sum_in_dollars():
    months = pd.date_range("2024-01-31", periods=8, freq="ME").strftime("%Y-%m-%d")
    entry = months[3]                             # Utilities enters here
    rows = []
    for base, (tk, cat) in enumerate(
            [("XLK", "Technology"), ("XLE", "Energy"), ("XLU", "Utilities")], start=1):
        for i, m in enumerate(months):
            if tk == "XLU" and i < 3:
                continue
            rows.append((tk, cat, m, 50.0 * np.sin(i + base) + 10.0 * base,
                         1000.0 * base + 30.0 * i))
    panel = _panel(rows)
    f_entrant = panel.loc[(panel["ticker"] == "XLU")
                          & (panel["month"] == entry), "F"].iloc[0]
    rel = relative_flow(category_panel(panel), panel).dropna(subset=["rel", "aum_prev"])
    for month, d in rel.groupby("month"):
        weighted = (d["aum_prev"] * d["rel"]).sum()
        scale = (d["aum_prev"] * d["rel"].abs()).sum()
        if month == entry:
            assert weighted == pytest.approx(-f_entrant)   # residual = entrant's flow
        elif scale > 0:
            assert abs(weighted) / scale < 1e-12, f"violated at {month}"


# --------------------------------------------------------------------------- #
# rotation turnover: T_t = matched legs of the conservation identity.
# --------------------------------------------------------------------------- #
def test_rotation_turnover_two_sector_hand_case():
    # M1: g_U = (10 - 2) / (100 + 300) = 0.02. R_Tech = 10 - 100*0.02 = +8,
    # R_Energy = -2 - 300*0.02 = -8 -> T = 8 dollars, tau = 8/400 = 0.02.
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 100.0),
        ("XLE", "Energy",     M0, 0.0, 300.0),
        ("XLK", "Technology", M1, 10.0, 112.0),
        ("XLE", "Energy",     M1, -2.0, 295.0),
    ])
    out = rotation_turnover(category_panel(panel), panel).set_index("month")
    assert out.loc[M1, "T"] == pytest.approx(8.0)
    assert out.loc[M1, "tau"] == pytest.approx(0.02)
    assert np.isnan(out.loc[M0, "T"])          # no prior assets at the first month


def test_rotation_turnover_pro_rata_flows_are_zero():
    # Flows exactly proportional to prior assets: pure tide, no rotation.
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 100.0),
        ("XLE", "Energy",     M0, 0.0, 300.0),
        ("XLK", "Technology", M1, 25.0, 130.0),
        ("XLE", "Energy",     M1, 75.0, 380.0),
    ])
    out = rotation_turnover(category_panel(panel), panel).set_index("month")
    assert out.loc[M1, "T"] == pytest.approx(0.0)


def test_rotation_turnover_partial_month_is_nan():
    # A category entering at M1 has no prior assets; the month must be NaN, not
    # a partial sum (which would understate T and break the leg equality).
    panel = _panel([
        ("XLK", "Technology", M0, 0.0, 100.0),
        ("XLE", "Energy",     M0, 0.0, 300.0),
        ("XLK", "Technology", M1, 10.0, 112.0),
        ("XLE", "Energy",     M1, -2.0, 295.0),
        ("XLF", "Financials", M1, 50.0, 500.0),
    ])
    out = rotation_turnover(category_panel(panel), panel).set_index("month")
    assert np.isnan(out.loc[M1, "T"])


def test_rotation_turnover_legs_match_independent_recomputation():
    # Independent path: R = F - A_prev * F_U/A_U from raw pivots. The positive
    # and negative legs must each equal T on a multi-month varying panel.
    panel = _multi_month_panel()
    cat = category_panel(panel)
    T = rotation_turnover(cat, panel).set_index("month")["T"].dropna()
    F = cat.pivot(index="month", columns="category", values="F")
    A = cat.pivot(index="month", columns="category", values="aum_prev")
    R = F.sub(A.div(A.sum(axis=1), axis=0).mul(F.sum(axis=1), axis=0)).loc[T.index]
    assert np.allclose(R.clip(lower=0).sum(axis=1), T)
    assert np.allclose(-R.clip(upper=0).sum(axis=1), T)
