"""Phase 3: aggregate per-fund flows to categories and form trailing windows.

Projects the aggregation and cumulative-flow equations of the methodology paper
(docs/fund-flow-rotation.tex) onto the persisted (ticker, month) panel:

    category flow      eq:category_flow   F_{c,t} = sum_{i in c} F_{i,t}
    category growth     eq:category_g     g_{c,t} = F_{c,t} / A_{c,t-1}
    whole-market growth eq:universe_g     g_{U,t} = sum_i F_{i,t} / sum_i A_{i,t-1}
    trailing cumulative eq:cumulative_flow CF_{c,t}(W) = sum_{k=0}^{W-1} F_{c,t-k}

Each fund currently maps to exactly one sector, so category_flow reduces to an
identity today; the machinery is written for the general many-funds-per-category
case and unit-tested as such, so enriching a sector with more funds later is a
data change (rows in universe.csv), not a code change.

Read-only over the panel; no network.
"""

import pandas as pd


def category_panel(panel):
    """Aggregate a per-fund (ticker, month) panel to a per-(category, month) panel.

    Sums member dollar flows and assets within each category and month, then
    normalizes by the prior month's category assets to get the category growth
    rate. The result is itself a tidy long frame keyed on (category, month), so
    the same rotation statistics apply to it as to a single fund.

    A category's prior assets A_{c,t-1} are summed over the funds present in month
    t-1, so a fund that starts mid-history simply joins the sum once its data
    begins; pre-data months contribute nothing (pandas sum skips NaN), matching
    the "fund enters when its filings begin" reading of the paper.

    @math_ref eq:category_flow
    @math_ref eq:category_g
    """
    cat = (panel.groupby(["category", "month"], as_index=False)
                .agg(F=("F", "sum"), aum=("aum", "sum"))
                .sort_values(["category", "month"])
                .reset_index(drop=True))
    cat["aum_prev"] = cat.groupby("category")["aum"].shift(1)
    cat["g"] = cat["F"] / cat["aum_prev"]
    return cat


def universe_g(panel):
    """Whole-market growth rate per month: total flow over total prior assets.

    This is the category aggregation taken over the single category containing
    every fund, and serves as the baseline that relative flow is measured against.

    @math_ref eq:universe_g
    """
    tot = (panel.groupby("month", as_index=False)
                .agg(F=("F", "sum"), aum=("aum", "sum"))
                .sort_values("month")
                .reset_index(drop=True))
    tot["aum_prev"] = tot["aum"].shift(1)
    tot["g_U"] = tot["F"] / tot["aum_prev"]
    return tot[["month", "g_U"]]


def cumulative_flow(cat, window):
    """Add trailing W-month cumulative dollar flow per category (column CF{window}).

    Monthly flow is noisy; the trailing sum over a window of `window` months shows
    the sustained trend. Defined only once a full window is available, so the first
    window-1 months of each category are NaN.

    @math_ref eq:cumulative_flow
    """
    cat = cat.sort_values(["category", "month"]).copy()
    cat[f"CF{window}"] = (cat.groupby("category")["F"]
                             .transform(lambda s: s.rolling(window, min_periods=window).sum()))
    return cat
