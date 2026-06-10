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
