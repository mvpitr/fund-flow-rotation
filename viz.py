"""Static matplotlib figures for the rotation metrics.

Each view answers one question, instead of packing strength, momentum, time, and
eleven sectors into a single chart:

    rrg_plot              where is every sector right now? (rotation snapshot)
    quadrant_timeline     how did it rotate? (quadrant occupied, sector x month)
    flow_heatmap          how strongly is each sector pulling flow, month by month?
    cumulative_flow_chart how many dollars? (trailing cumulative flow, magnitude)
    rrg_small_multiples   one sector's full path, in isolation (detail view)

RRG stands for relative rotation graph: the strength-vs-momentum chart built by
rotation.rrg_coordinates, whose four quadrants (leading / weakening / lagging /
improving) name a sector's rotation phase. "Provisional" marks the newest month,
whose filings may not all have posted yet.

Plotting only -- the math lives in categories.py / rotation.py, so no @math_ref
here. Each function returns a matplotlib Figure; the CLI writes PNGs to
docs/figures/. Styling is deliberately minimal for now.
"""

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")          # headless: render to files, never open a window
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch, Rectangle
import numpy as np
import pandas as pd

from categories import category_panel, cumulative_flow
from rotation import rrg_coordinates

DB_PATH = "data/flows.db"
FIG_DIR = "docs/figures"
B = 1e9


# Rotation-graph quadrants, keyed by (rs >= 0, rs_mom >= 0): name and colour.
# Listed in rotation order (the clockwise path a sector typically traces).
QUADRANTS = {
    (True, True): ("leading", "#2ca02c"),
    (True, False): ("weakening", "#e6a000"),
    (False, False): ("lagging", "#d62728"),
    (False, True): ("improving", "#1f77b4"),
}


def _rrg_panel(panel, smooth, lookback, lag):
    """RRG coordinates pivoted to two aligned sector x month grids (rs, rs_mom).

    Rows are sorted with the strongest current relative strength on top; leading
    warm-up months -- those consumed by the smoothing and lookback windows before
    rs is defined for any sector -- are dropped. Shared by the heatmap and the
    quadrant timeline (static and interactive).
    """
    cat = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag)
    rs = cat.pivot(index="category", columns="month", values="rs")
    rs = rs.sort_values(rs.columns.max(), ascending=False)
    mom = cat.pivot(index="category", columns="month", values="rs_mom").reindex(
        index=rs.index, columns=rs.columns)
    live = rs.columns[rs.notna().any(axis=0).to_numpy()]
    return rs[live], mom[live]


def flow_heatmap(panel, smooth=3, lookback=12, lag=3, vmax=None):
    """Heatmap of smoothed relative strength (RS-Ratio) by sector and month.

    Colours each sector-month by its standardized, smoothed relative flow rs
    (eq:rs_ratio): blue = gaining share of flow, red = losing it. Smoothing turns
    the month-to-month flicker of raw flow into coherent bands, and standardizing
    makes one colour intensity mean the same thing in every cell. Rows are sorted
    with the strongest current inflows on top. The last (provisional) month is
    fenced with a dashed divider; the scale saturates at `vmax` (default 97.5th
    percentile of |rs|).
    """
    wide, _ = _rrg_panel(panel, smooth, lookback, lag)
    Z = wide.to_numpy(dtype=float)
    if vmax is None:
        vmax = float(np.nanpercentile(np.abs(Z), 97.5))

    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.imshow(Z, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(wide.index)))
    ax.set_yticklabels(wide.index)
    months = pd.to_datetime(wide.columns)
    ticks = [i for i, m in enumerate(months) if m.month == 1]      # year boundaries
    ax.set_xticks(ticks)
    ax.set_xticklabels([months[i].strftime("%Y") for i in ticks])
    ax.axvline(len(months) - 1.5, color="black", lw=0.8, ls="--")  # provisional fence
    fig.colorbar(im, ax=ax, label="relative strength (smoothed, standardized)")
    ax.set_title("Sector relative-strength heatmap  (smoothed; blue gaining / red losing; "
                 "last month provisional)")
    fig.tight_layout()
    return fig


def cumulative_flow_chart(panel, window=6):
    """Small-multiple line charts of trailing W-month cumulative dollar flow.

    Kept in dollars on purpose: this is the magnitude view, the counterweight to
    the standardized heatmap and rotation graph. One panel per sector avoids the
    spaghetti of overplotting eleven lines on one axis.
    """
    cat = cumulative_flow(category_panel(panel), window=window)
    col = f"CF{window}"
    sectors = sorted(cat["category"].unique())
    ncol = 4
    nrow = int(np.ceil(len(sectors) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3 * ncol, 2 * nrow), sharex=True)
    axes = np.atleast_1d(axes).ravel()
    for ax, sec in zip(axes, sectors):
        d = cat[cat["category"] == sec]
        ax.plot(pd.to_datetime(d["month"]), d[col] / B, lw=1)
        ax.axhline(0, color="grey", lw=0.6)
        ax.set_title(sec, fontsize=8)
        ax.tick_params(labelsize=6)
    for ax in axes[len(sectors):]:
        ax.set_visible(False)
    fig.suptitle(f"Trailing {window}-month cumulative flow by sector ($B)")
    fig.tight_layout()
    return fig


def rrg_plot(panel, smooth=3, lookback=12, lag=3, tail=3):
    """Rotation snapshot: every sector at its latest (rs, rs_mom), coloured by quadrant.

    One dot per sector at the latest month. Colour says which quadrant the sector
    occupies (the ticker label carries identity), and a short grey comet fading
    over the prior `tail` months says which way it is moving. Axis limits frame
    only what is drawn, so an old excursion cannot compress the current picture.
    History lives in quadrant_timeline and rrg_small_multiples; keeping it out of
    this chart is what keeps the chart readable. Axes are equal-aspect and
    symmetric about the origin, the true neutral point, so quadrant membership is
    not a visual artifact of scaling.
    """
    out = rrg_coordinates(category_panel(panel), panel, smooth=smooth,
                          lookback=lookback, lag=lag).dropna(subset=["rs", "rs_mom"])
    months = sorted(out["month"].unique())
    sub = out[out["month"].isin(months[-(tail + 1):])]
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()
    paths = []
    for sec in sorted(sub["category"].unique()):
        d = sub[sub["category"] == sec].sort_values("month")
        paths.append((d["rs"].to_numpy(), d["rs_mom"].to_numpy(), ticker.get(sec, sec)))
    # Frame the axes on the heads only: a comet that wandered far away clips at the
    # border instead of compressing the current picture.
    head_max = max((max(abs(xs[-1]), abs(ys[-1])) for xs, ys, _ in paths), default=1.0)
    lim = head_max * 1.2 or 1.0

    fig, ax = plt.subplots(figsize=(7, 7))
    _quadrant_patches(ax, lim)
    heads = []
    for xs, ys, tick in paths:
        for k in range(1, len(xs)):              # grey comet, old faint -> new solid
            ax.plot(xs[k - 1:k + 1], ys[k - 1:k + 1], "-", color="0.45", lw=1.1,
                    alpha=0.12 + 0.38 * k / max(len(xs) - 1, 1), zorder=1)
        x, y = float(xs[-1]), float(ys[-1])
        _, color = QUADRANTS[(x >= 0, y >= 0)]
        ax.plot(x, y, "o", color=color, ms=10, mec="white", mew=0.9, zorder=3)
        heads.append((x, y, tick))
    _label_heads(ax, heads, lim)

    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)
    for (pos_rs, pos_mom), (name, color) in QUADRANTS.items():
        x, y = lim if pos_rs else -lim, lim if pos_mom else -lim
        ax.text(x * 0.97, y * 0.97, name, ha="right" if pos_rs else "left",
                va="top" if pos_mom else "bottom", fontsize=9, color=color, alpha=0.8)
    ax.set_xlabel("RS-Ratio  (standardized relative flow)")
    ax.set_ylabel("RS-Momentum  (3-month change)")
    ax.set_title(f"Sector rotation snapshot  ({pd.to_datetime(months[-1]).date()}; "
                 f"{tail}-month comet; latest provisional)")
    fig.tight_layout()
    return fig


def _label_heads(ax, heads, lim):
    """Ticker labels beside the snapshot dots, nudged out of each other's way.

    Greedy placement: each label tries eight offsets around its dot and keeps the
    one farthest from the labels already placed and from the other dots -- enough
    to stop collisions in a tight cluster without a full layout engine.
    """
    candidates = [(8, 6, "left"), (8, -12, "left"), (-8, 6, "right"), (-8, -12, "right"),
                  (0, 10, "center"), (0, -16, "center"), (13, -3, "left"), (-13, -3, "right")]
    pt = lim / 252.0                             # approx data units per point (7in axes)
    placed = []
    for x, y, label in sorted(heads, key=lambda h: (h[1], h[0])):
        obstacles = placed + [(hx, hy) for hx, hy, _ in heads if (hx, hy) != (x, y)]
        dx, dy, ha = max(candidates, key=lambda c: min(
            [np.hypot(x + c[0] * pt - px, y + c[1] * pt - py) for px, py in obstacles]
            or [1.0]))
        placed.append((x + dx * pt, y + dy * pt))
        ax.annotate(label, (x, y), xytext=(dx, dy), textcoords="offset points",
                    fontsize=7.5, color="0.15", ha=ha, zorder=4)


def _quadrant_patches(ax, lim):
    """Shade the four rotation quadrants on `ax` (drawn below the data)."""
    for (pos_rs, pos_mom), (_, fc) in QUADRANTS.items():
        x0, y0 = (0 if pos_rs else -lim), (0 if pos_mom else -lim)
        ax.add_patch(Rectangle((x0, y0), lim, lim, color=fc, alpha=0.06, zorder=0))


def quadrant_timeline(panel, smooth=3, lookback=12, lag=3):
    """Rotation history at a glance: sector x month grid coloured by quadrant.

    Each cell shows which rotation-graph quadrant the sector occupied that month
    (leading green, weakening amber, lagging red, improving blue); colour
    intensity scales with the distance from the origin, so pale cells mean a weak
    signal. This replaces the long tangled tails of a rotation graph with one
    readable strip per sector. Rows sorted with the strongest current relative
    strength on top; the last (provisional) month is fenced with a dashed divider.
    """
    rs, mom = _rrg_panel(panel, smooth, lookback, lag)
    RS, M = rs.to_numpy(dtype=float), mom.to_numpy(dtype=float)
    radius = np.hypot(RS, M)
    scale = float(np.nanpercentile(radius, 90)) or 1.0
    strength = np.clip(radius / scale, 0.0, 1.0)

    img = np.zeros(RS.shape + (4,))
    valid = ~np.isnan(radius)
    for (pos_rs, pos_mom), (_, hexc) in QUADRANTS.items():
        mask = valid & ((RS >= 0) == pos_rs) & ((M >= 0) == pos_mom)
        img[mask, :3] = to_rgb(hexc)
    # Quadratic in strength: months near the origin fade to near-white, so only
    # episodes with a real signal carry colour and the strip stays readable.
    img[..., 3] = np.where(valid, 0.06 + 0.94 * strength ** 2, 0.0)

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.imshow(img, aspect="auto", interpolation="nearest")
    ax.set_yticks(range(len(rs.index)))
    ax.set_yticklabels(rs.index)
    months = pd.to_datetime(rs.columns)
    ticks = [i for i, m in enumerate(months) if m.month == 1]      # year boundaries
    ax.set_xticks(ticks)
    ax.set_xticklabels([months[i].strftime("%Y") for i in ticks])
    ax.axvline(len(months) - 1.5, color="black", lw=0.8, ls="--")  # provisional fence
    handles = [Patch(facecolor=c, label=n) for n, c in QUADRANTS.values()]
    ax.legend(handles=handles, ncols=4, loc="lower right", bbox_to_anchor=(1.0, 1.01),
              frameon=False, fontsize=7, handlelength=1.0, columnspacing=1.0)
    ax.set_title("Sector rotation timeline  (pale = weak signal; last month provisional)",
                 loc="left", fontsize=10)
    fig.tight_layout()
    return fig


def rrg_small_multiples(panel, smooth=3, lookback=12, lag=3, tail=12):
    """Grid of per-sector rotation graphs -- one clean mini-RRG per sector.

    Splits the crowded all-sector RRG so each sector's path is readable in
    isolation. Every panel shares the same axes (comparable across sectors), shades
    the four quadrants, and fades the trail from old (faint) to current (solid), the
    final point marked. A longer tail than the combined chart is legible here
    because only one sector occupies each panel.
    """
    out = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag).dropna(subset=["rs", "rs_mom"])
    months = sorted(out["month"].unique())
    sub = out[out["month"].isin(months[-(tail + 1):])]
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()
    sectors = sorted(sub["category"].unique())
    vals = sub[["rs", "rs_mom"]].to_numpy()
    lim = (float(np.nanmax(np.abs(vals))) if len(vals) else 1.0) * 1.1 or 1.0

    ncol = 4
    nrow = int(np.ceil(len(sectors) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(2.7 * ncol, 2.7 * nrow),
                             sharex=True, sharey=True)
    axes = np.atleast_1d(axes).ravel()
    cmap = plt.get_cmap("tab20")
    for i, (ax, sec) in enumerate(zip(axes, sectors)):
        _quadrant_patches(ax, lim)
        d = sub[sub["category"] == sec].sort_values("month")
        xs, ys = d["rs"].to_numpy(), d["rs_mom"].to_numpy()
        color = cmap(i % 20)
        for k in range(1, len(xs)):                       # trail, faint (old) -> solid (new)
            ax.plot(xs[k - 1:k + 1], ys[k - 1:k + 1], "-", color=color, lw=1.3,
                    alpha=0.15 + 0.65 * k / max(len(xs) - 1, 1))
        if len(xs):
            ax.plot(xs[-1], ys[-1], "o", color=color, ms=8, mec="white", mew=0.8)
        ax.axhline(0, color="black", lw=0.6)
        ax.axvline(0, color="black", lw=0.6)
        ax.set_title(f"{ticker.get(sec, sec)}  {sec}", fontsize=7)
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.tick_params(labelsize=6)
    for ax in axes[len(sectors):]:
        ax.set_visible(False)
    fig.suptitle(f"Per-sector rotation paths  ({pd.to_datetime(months[-1]).date()}; "
                 f"{tail}-month tail; latest provisional)")
    fig.supxlabel("RS-Ratio  (standardized relative flow)", fontsize=9)
    fig.supylabel("RS-Momentum  (3-month change)", fontsize=9)
    fig.tight_layout()
    return fig


def _load(db_path=DB_PATH):
    con = sqlite3.connect(db_path)
    panel = pd.read_sql("SELECT * FROM monthly_flows", con, parse_dates=["month"])
    con.close()
    return panel


def _figures(db_path=DB_PATH, out_dir=FIG_DIR):
    panel = _load(db_path)
    os.makedirs(out_dir, exist_ok=True)
    figs = {
        "rrg": rrg_plot(panel),
        "rotation_timeline": quadrant_timeline(panel),
        "heatmap": flow_heatmap(panel),
        "cumulative_flow": cumulative_flow_chart(panel),
        "rrg_small_multiples": rrg_small_multiples(panel),
    }
    for name, fig in figs.items():
        path = os.path.join(out_dir, f"{name}.png")
        fig.savefig(path, dpi=150)
        print(f"saved -> {path}")


if __name__ == "__main__":
    _figures()
