"""Phase 4: rotation statistics on the category panel.

Rotation is the movement of capital between sectors over time. These functions
project the paper's rotation equations (docs/fund-flow-rotation.tex, section
Rotation) onto the per-(category, month) panel produced by categories.py:

    relative flow   eq:relative_flow   rel_{c,t} = g_{c,t} - g_{U,t}
    standardized    eq:zscore          z_{c,t}   = (g_{c,t} - mu_L) / sigma_L
    momentum         eq:momentum        m_{c,t}   = rel_{c,t} - rel_{c,t-D}

Read-only over the panel; no network.
"""

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


def z_score(cat, lookback=12):
    """Add standardized flow z_{c,t} = (g_{c,t} - mu_L) / sigma_L (column 'z').

    mu_L and sigma_L are the mean and sample standard deviation of g over the
    `lookback` months strictly BEFORE t (the current month is excluded, so a spike
    never standardizes against itself and the score has no upper bound). Defined
    only once a full prior window of `lookback` months exists, and NaN where
    sigma_L is zero (a perfectly flat history).

    @math_ref eq:zscore
    """
    cat = cat.sort_values(["category", "month"]).copy()
    # Shift by one so the window ending at t covers g over [t-lookback, t-1].
    prior = cat.groupby("category")["g"].shift(1).groupby(cat["category"])
    mu = prior.transform(lambda s: s.rolling(lookback, min_periods=lookback).mean())
    sd = prior.transform(lambda s: s.rolling(lookback, min_periods=lookback).std())
    cat["z"] = (cat["g"] - mu) / sd.where(sd != 0)
    return cat
