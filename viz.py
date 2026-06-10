"""Phase 5: static matplotlib figures for the rotation metrics.

Three views, each built straight from the per-fund panel and matched to what its
metric honestly represents:

    flow_heatmap          standardized flow z by sector and month (the panel)
    cumulative_flow_chart trailing cumulative dollar flow per sector (magnitude)
    rrg_plot              rotation graph: RS-Ratio (x) vs RS-Momentum (y)

Plotting only -- the math lives in categories.py / rotation.py, so no @math_ref
here. Each function returns a matplotlib Figure; the CLI writes PNGs to
docs/figures/. Styling is deliberately minimal for now.
"""

import os
import sqlite3

import matplotlib
matplotlib.use("Agg")          # headless: render to files, never open a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from categories import category_panel, cumulative_flow
from rotation import z_score, rrg_coordinates

DB_PATH = "data/flows.db"
FIG_DIR = "docs/figures"
B = 1e9


def flow_heatmap(panel, lookback=12):
    """Heatmap of standardized flow z by sector (rows) and month (columns).

    Diverging palette centered at zero (blue = inflow, red = outflow). z is used
    rather than dollar flow so one colour intensity means the same thing in every
    cell, across both sectors and time. The last (provisional) month is fenced off
    with a dashed divider.
    """
    cat = z_score(category_panel(panel), lookback=lookback)
    wide = cat.pivot(index="category", columns="month", values="z")
    wide = wide.sort_values(wide.columns.max(), ascending=False)  # strongest inflow on top
    Z = wide.to_numpy(dtype=float)
    vmax = np.nanmax(np.abs(Z))

    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.imshow(Z, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(wide.index)))
    ax.set_yticklabels(wide.index)
    months = pd.to_datetime(wide.columns)
    ticks = [i for i, m in enumerate(months) if m.month == 1]      # year boundaries
    ax.set_xticks(ticks)
    ax.set_xticklabels([months[i].strftime("%Y") for i in ticks])
    ax.axvline(len(months) - 1.5, color="black", lw=0.8, ls="--")  # provisional fence
    fig.colorbar(im, ax=ax, label="standardized flow z")
    ax.set_title("Sector flow heatmap  (standardized z; blue inflow / red outflow; "
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


def rrg_plot(panel, lookback=12, lag=3, tail=6):
    """Rotation graph: RS-Ratio (x) vs RS-Momentum (y), with a per-sector tail.

    Each sector is a point at its latest (rs, rs_mom); the line traces the prior
    `tail` months, so the path shows the rotation. Axes are equal-aspect and
    symmetric about the origin, the true neutral point, so quadrant membership is
    not a visual artifact of scaling. Quadrants: leading / weakening / lagging /
    improving (clockwise).
    """
    out = rrg_coordinates(category_panel(panel), panel, lookback=lookback, lag=lag)
    months = sorted(out["month"].unique())
    sub = out[out["month"].isin(months[-(tail + 1):])].dropna(subset=["rs", "rs_mom"])

    fig, ax = plt.subplots(figsize=(7, 7))
    cmap = plt.get_cmap("tab20")
    lim = 0.0
    for i, sec in enumerate(sorted(sub["category"].unique())):
        d = sub[sub["category"] == sec].sort_values("month")
        color = cmap(i % 20)
        ax.plot(d["rs"], d["rs_mom"], "-", color=color, lw=1, alpha=0.6)
        last = d.iloc[-1]
        ax.plot(last["rs"], last["rs_mom"], "o", color=color, ms=8)
        ax.annotate(sec, (last["rs"], last["rs_mom"]), fontsize=7,
                    xytext=(4, 4), textcoords="offset points")
        lim = max(lim, d["rs"].abs().max(), d["rs_mom"].abs().max())
    lim = (lim or 1.0) * 1.1

    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(0, color="black", lw=0.8)
    for (x, y, ha, va, label) in [
        (lim, lim, "right", "top", "leading"),
        (lim, -lim, "right", "bottom", "weakening"),
        (-lim, -lim, "left", "bottom", "lagging"),
        (-lim, lim, "left", "top", "improving"),
    ]:
        ax.text(x * 0.97, y * 0.97, label, ha=ha, va=va, fontsize=9, color="grey")
    ax.set_xlabel("RS-Ratio  (standardized relative flow)")
    ax.set_ylabel("RS-Momentum  (3-month change)")
    ax.set_title(f"Sector rotation graph  ({pd.to_datetime(months[-1]).date()}; "
                 f"{tail}-month tail; latest provisional)")
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
        "heatmap": flow_heatmap(panel),
        "cumulative_flow": cumulative_flow_chart(panel),
        "rrg": rrg_plot(panel),
    }
    for name, fig in figs.items():
        path = os.path.join(out_dir, f"{name}.png")
        fig.savefig(path, dpi=150)
        print(f"saved -> {path}")


if __name__ == "__main__":
    _figures()
