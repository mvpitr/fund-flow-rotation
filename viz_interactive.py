"""Phase 5: interactive Plotly rotation graph (web showcase).

A Relative Rotation Graph with a month slider: scrub through time and watch each
sector trace its path through the leading / weakening / lagging / improving
quadrants. Reuses rrg_coordinates from rotation.py (the RS-Ratio / RS-Momentum
math lives there and in the paper), so this module is plotting only -- no
@math_ref. Sector legend entries toggle by group, so a cluttered all-sector view
can be thinned to the few sectors of interest.

The CLI writes a self-contained HTML file to docs/figures/rrg_interactive.html.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.colors import hex_to_rgb
from plotly.subplots import make_subplots

from categories import category_panel
from rotation import rrg_coordinates
from viz import DB_PATH, FIG_DIR, _load

# A distinct colour per sector (qualitative palette).
_PALETTE = px.colors.qualitative.Alphabet


def _rgba(hexc, alpha):
    r, g, b = hex_to_rgb(hexc)
    return f"rgba({r},{g},{b},{alpha})"


def _sector_tail(d, upto_idx, months, tail):
    """Coordinates of one sector's tail ending at months[upto_idx]."""
    window = months[max(0, upto_idx - tail): upto_idx + 1]
    sub = d[d["month"].isin(window)].sort_values("month")
    return sub["rs"].to_numpy(), sub["rs_mom"].to_numpy()


def rrg_interactive(panel, smooth=3, lookback=12, lag=3, tail=3):
    """Return an animated Plotly rotation graph (RS-Ratio x, RS-Momentum y).

    One animation frame per month. Each sector shows a faint trailing-`tail`-month
    trail and a solid, ticker-labelled head at the current month; the slider and
    Play button carry the rotation, so the trails stay short and uncluttered.
    Quadrants are shaded for orientation and the legend toggles sectors by group.
    Axes are equal-aspect and symmetric about the origin, the neutral point.
    """
    out = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag)
    out = out.dropna(subset=["rs", "rs_mom"])
    sectors = sorted(out["category"].unique())
    months = sorted(out["month"].unique())
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()
    lim = float(np.nanmax(np.abs(out[["rs", "rs_mom"]].to_numpy()))) * 1.08 or 1.0
    color = {sec: _PALETTE[i % len(_PALETTE)] for i, sec in enumerate(sectors)}

    def traces_for(month):
        idx = months.index(month)
        data = []
        for sec in sectors:
            d = out[out["category"] == sec]
            x, y = _sector_tail(d, idx, months, tail)
            c = color[sec]
            data.append(go.Scatter(                      # faint trail
                x=x, y=y, mode="lines",
                line=dict(color=_rgba(c, 0.35), width=1.5),
                legendgroup=sec, showlegend=False, hoverinfo="skip"))
            data.append(go.Scatter(                      # solid, ticker-labelled head
                x=x[-1:], y=y[-1:], mode="markers+text",
                marker=dict(color=c, size=12, line=dict(color="white", width=1)),
                text=[ticker.get(sec, sec)] if len(x) else [],
                textposition="top center", textfont=dict(size=9, color=c),
                name=sec, legendgroup=sec, showlegend=True,
                hovertemplate=f"{sec}<br>RS=%{{x:.2f}}<br>mom=%{{y:.2f}}<extra></extra>"))
        return data

    fig = go.Figure(
        data=traces_for(months[-1]),
        frames=[go.Frame(data=traces_for(m), name=str(pd.Timestamp(m).date()))
                for m in months],
    )

    # Shaded quadrants, drawn below the data, for at-a-glance orientation.
    for x0, x1, y0, y1, fill in [
        (0, lim, 0, lim, _rgba("#2ca02c", 0.06)),        # leading   (top-right)
        (0, lim, -lim, 0, _rgba("#e6a000", 0.06)),       # weakening (bottom-right)
        (-lim, 0, -lim, 0, _rgba("#d62728", 0.06)),      # lagging   (bottom-left)
        (-lim, 0, 0, lim, _rgba("#1f77b4", 0.06)),       # improving (top-left)
    ]:
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=fill, line=dict(width=0), layer="below")
    fig.add_hline(y=0, line=dict(color="black", width=1))
    fig.add_vline(x=0, line=dict(color="black", width=1))
    for x, y, ax_, ay, label in [
        (lim, lim, "right", "top", "leading"),
        (lim, -lim, "right", "bottom", "weakening"),
        (-lim, -lim, "left", "bottom", "lagging"),
        (-lim, lim, "left", "top", "improving"),
    ]:
        fig.add_annotation(x=x, y=y, text=label, showarrow=False,
                           xanchor=ax_, yanchor=ay, font=dict(color="grey", size=12))

    steps = [dict(method="animate", label=f.name,
                  args=[[f.name], dict(mode="immediate",
                                       frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))])
             for f in fig.frames]
    fig.update_layout(
        title="Sector rotation graph (RS-Ratio vs RS-Momentum; latest month provisional)",
        xaxis=dict(title="RS-Ratio (standardized relative flow)", range=[-lim, lim], zeroline=False),
        yaxis=dict(title="RS-Momentum (3-month change)", range=[-lim, lim], zeroline=False,
                   scaleanchor="x", scaleratio=1),
        width=780, height=780, template="plotly_white",
        legend=dict(groupclick="togglegroup", title="sector"),
        sliders=[dict(active=len(steps) - 1, steps=steps, x=0, len=1.0,
                      currentvalue=dict(prefix="month: "))],
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.12,
                          buttons=[dict(label="Play", method="animate",
                                        args=[None, dict(fromcurrent=True,
                                                         frame=dict(duration=400, redraw=True),
                                                         transition=dict(duration=0))])])],
    )
    return fig


def rrg_small_multiples_interactive(panel, smooth=3, lookback=12, lag=3, tail=12):
    """Grid of per-sector interactive rotation graphs -- one mini-RRG per sector.

    Splits the crowded all-sector RRG so each sector's path reads in isolation; all
    panels share the same axes for comparison and shade the four quadrants. The
    trail fades old to current, the head marked; hover any point for its RS values.
    """
    out = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag).dropna(subset=["rs", "rs_mom"])
    months = sorted(out["month"].unique())
    sub = out[out["month"].isin(months[-(tail + 1):])]
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()
    sectors = sorted(sub["category"].unique())
    vals = sub[["rs", "rs_mom"]].to_numpy()
    lim = (float(np.nanmax(np.abs(vals))) if len(vals) else 1.0) * 1.1 or 1.0
    color = {sec: _PALETTE[i % len(_PALETTE)] for i, sec in enumerate(sectors)}

    ncol = 4
    nrow = int(np.ceil(len(sectors) / ncol))
    fig = make_subplots(rows=nrow, cols=ncol, horizontal_spacing=0.03, vertical_spacing=0.09,
                        subplot_titles=[f"{ticker.get(s, s)}  {s}" for s in sectors])
    quads = [(0, lim, 0, lim, "#2ca02c"), (0, lim, -lim, 0, "#e6a000"),
             (-lim, 0, -lim, 0, "#d62728"), (-lim, 0, 0, lim, "#1f77b4")]
    for idx, sec in enumerate(sectors):
        r, c = idx // ncol + 1, idx % ncol + 1
        for x0, x1, y0, y1, fc in quads:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                          fillcolor=_rgba(fc, 0.06), line_width=0, layer="below", row=r, col=c)
        fig.add_hline(y=0, line=dict(color="black", width=0.6), row=r, col=c)
        fig.add_vline(x=0, line=dict(color="black", width=0.6), row=r, col=c)
        d = sub[sub["category"] == sec].sort_values("month")
        col = color[sec]
        fig.add_trace(go.Scatter(x=d["rs"], y=d["rs_mom"], mode="lines",
                                 line=dict(color=_rgba(col, 0.5), width=1.5),
                                 showlegend=False, hoverinfo="skip"), row=r, col=c)
        fig.add_trace(go.Scatter(x=d["rs"].iloc[-1:], y=d["rs_mom"].iloc[-1:], mode="markers",
                                 marker=dict(color=col, size=10, line=dict(color="white", width=1)),
                                 showlegend=False,
                                 hovertemplate=f"{sec}<br>RS=%{{x:.2f}}<br>mom=%{{y:.2f}}<extra></extra>"),
                      row=r, col=c)

    fig.update_xaxes(range=[-lim, lim], showticklabels=False, showgrid=False, zeroline=False)
    fig.update_yaxes(range=[-lim, lim], showticklabels=False, showgrid=False, zeroline=False)
    cell = 230
    fig.update_layout(
        title="Per-sector rotation paths  (RS-Ratio x vs RS-Momentum y; latest month provisional)",
        width=ncol * cell + 80, height=nrow * cell + 120,
        template="plotly_white", margin=dict(l=40, r=20, t=80, b=40))
    for ann in fig.layout.annotations:           # shrink the subplot titles
        ann.font.size = 11
    return fig


def _write(db_path=DB_PATH, out_dir=FIG_DIR):
    import os
    os.makedirs(out_dir, exist_ok=True)
    fig = rrg_small_multiples_interactive(_load(db_path))
    path = os.path.join(out_dir, "rrg_interactive.html")
    # Fixed div_id so identical data yields byte-identical HTML (Plotly otherwise
    # stamps a random id), letting deploy.sh skip no-op publishes.
    fig.write_html(path, include_plotlyjs="cdn", div_id="rrg")
    print(f"saved -> {path}")


if __name__ == "__main__":
    _write()
