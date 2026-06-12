"""Rotation statistics on the category panel.

Rotation is the movement of capital between sectors over time. These functions
project the paper's rotation equations (docs/fund-flow-rotation.tex, section
Rotation) onto the per-(category, month) panel produced by categories.py:

    relative flow   eq:relative_flow      rel_{c,t} = g_{c,t} - g_{U,t}
    standardized    eq:zscore             z_{c,t}   = (g_{c,t} - mu_L) / sigma_L
    momentum        eq:momentum           m_{c,t}   = rel_{c,t} - rel_{c,t-D}
    turnover        eq:rotation_turnover  T_t = (1/2) sum_c |A_{c,t-1} rel_{c,t}|

The rotation-graph coordinates (eq:rel_smoothed, eq:rs_ratio, eq:rs_momentum) smooth
relative flow with a trailing mean, then apply the same standardization and momentum
operators to it; see rrg_coordinates. Read-only over the panel; no network.
"""

import pandas as pd

from categories import universe_g


def relative_flow(cat, panel):
    """Add relative flow rel_{c,t} = g_{c,t} - g_{U,t} (column 'rel').

    Subtracts the whole-market growth baseline from each category's growth, so a
    market-wide tide cancels and only genuine reallocation between sectors remains.
    A positive value means the sector drew more than its market-weighted share of
    flow that month. `panel` is the per-fund panel (used to form g_U over the full
    universe); `cat` is its category aggregation from categories.category_panel.

    @math_ref eq:relative_flow
    """
    g_U = universe_g(panel).set_index("month")["g_U"]
    cat = cat.copy()
    cat["rel"] = cat["g"] - cat["month"].map(g_U)
    return cat


def z_score(cat, col="g", lookback=12, out="z"):
    """Standardize `col` against its own strictly-prior history (column `out`).

    z = (col_t - mu_L) / sigma_L, where mu_L and sigma_L are the mean and sample
    standard deviation of `col` over the `lookback` months strictly BEFORE t (the
    current month is excluded, so a spike never standardizes against itself and the
    score has no upper bound). Defined only once a full prior window of `lookback`
    months exists, and NaN where sigma_L is zero (a perfectly flat history).

    Defaults standardize the category growth g into 'z'; passing col='rel',
    out='rs' forms the rotation-graph relative strength (see rrg_coordinates).

    @math_ref eq:zscore
    """
    cat = cat.sort_values(["category", "month"]).copy()
    # Shift by one so the window ending at t covers `col` over [t-lookback, t-1].
    prior = cat.groupby("category")[col].shift(1).groupby(cat["category"])
    mu = prior.transform(lambda s: s.rolling(lookback, min_periods=lookback).mean())
    sd = prior.transform(lambda s: s.rolling(lookback, min_periods=lookback).std())
    cat[out] = (cat[col] - mu) / sd.where(sd != 0)
    return cat


def momentum(cat, col="rel", lag=3, out="mom"):
    """Add the change in `col` over `lag` months, per category (column `out`).

    m = col_t - col_{t-lag}: whether the quantity is rising or fading, regardless
    of its current level. Defaults take the momentum of relative flow into 'mom';
    passing col='rs', out='rs_mom' forms the rotation-graph vertical axis. Requires
    `col` to be present; NaN for the first `lag` months of each category.

    @math_ref eq:momentum
    """
    if col not in cat.columns:
        raise ValueError(f"momentum needs the '{col}' column; compute it first.")
    cat = cat.sort_values(["category", "month"]).copy()
    cat[out] = cat.groupby("category")[col].diff(lag)
    return cat


def rrg_coordinates(cat, panel, smooth=3, lookback=12, lag=3):
    """Add the rotation-graph coordinates 'rel_bar', 'rs' and 'rs_mom'.

    Relative flow is first smoothed with a trailing `smooth`-month mean into rel_bar
    (eq:rel_smoothed), so a single noisy month does not dominate the path; rel_bar
    is then standardized against its own recent history into the relative strength
    rs (eq:rs_ratio), putting every sector on a common scale, and rs_mom is its
    momentum (eq:rs_momentum). The rotation graph plots rs (horizontal, relative
    strength) against rs_mom (vertical, whether that strength is rising or fading).
    `smooth=1` leaves relative flow unsmoothed. `panel` is the per-fund panel,
    needed to form the market baseline g_U inside relative_flow.

    @math_ref eq:rel_smoothed
    @math_ref eq:rs_ratio
    @math_ref eq:rs_momentum
    """
    cat = relative_flow(cat, panel)
    cat = cat.sort_values(["category", "month"]).copy()
    if smooth > 1:
        cat["rel_bar"] = cat.groupby("category")["rel"].transform(
            lambda s: s.rolling(smooth, min_periods=smooth).mean())
    else:
        cat["rel_bar"] = cat["rel"]
    cat = z_score(cat, col="rel_bar", lookback=lookback, out="rs")
    cat = momentum(cat, col="rs", lag=lag, out="rs_mom")
    return cat


def rotation_turnover(cat, panel):
    """Gross rotation turnover: the dollars that moved between categories each month.

    The dollar rotation flow R_{c,t} = A_{c,t-1} rel_{c,t} = F_{c,t} - A_{c,t-1} g_{U,t}
    is a category's flow in excess of its assets growing at the universe rate. By the
    conservation identity the R sum to zero each month, so half their absolute sum
    T_t is the matched size of the positive and negative legs -- the money actually
    rotating -- and tau_t = T_t / sum_c A_{c,t-1} is that as a fraction of prior
    universe assets. Computed on raw monthly relative flow, where the cancellation
    is exact. Months where any category lacks rel or prior assets are NaN, not
    partial sums: a partial sum understates T and breaks the leg equality. Returns
    one row per month with columns 'T' (dollars) and 'tau' (rate).

    @math_ref eq:rotation_dollars
    @math_ref eq:rotation_turnover
    """
    cat = relative_flow(cat, panel)
    rel = cat.pivot(index="month", columns="category", values="rel")
    A = cat.pivot(index="month", columns="category", values="aum_prev")
    R = A * rel
    T = (0.5 * R.abs().sum(axis=1)).where(R.notna().all(axis=1))
    tau = T / A.sum(axis=1)
    return pd.DataFrame({"month": T.index, "T": T.values, "tau": tau.values})
