"""Phase 5: interactive Plotly rotation figures (web showcase).

Two views on one self-contained page, the interactive twins of the static
figures in viz.py:

    rrg_interactive                animated rotation graph: one quadrant-coloured
                                   dot per sector, a short grey comet, and a month
                                   slider that carries the history so the chart
                                   itself stays clean
    quadrant_timeline_interactive  rotation history: sector x month strip coloured
                                   by quadrant, hover for exact values

Reuses rrg_coordinates from rotation.py (the RS-Ratio / RS-Momentum math lives
there and in the paper), so this module is plotting only -- no @math_ref.
The CLI writes a self-contained HTML page to docs/figures/rrg_interactive.html.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.colors import hex_to_rgb

from categories import category_panel
from rotation import rrg_coordinates
from viz import DB_PATH, FIG_DIR, QUADRANTS, _load, _rrg_panel


def _rgba(hexc, alpha):
    r, g, b = hex_to_rgb(hexc)
    return f"rgba({r},{g},{b},{alpha})"


def _pale(hexc, keep=0.12):
    """Blend a colour toward white, keeping `keep` of its saturation."""
    r, g, b = hex_to_rgb(hexc)
    mix = [round(255 - (255 - v) * keep) for v in (r, g, b)]
    return f"rgb({mix[0]},{mix[1]},{mix[2]})"


def _sector_tail(d, upto_idx, months, tail):
    """Coordinates of one sector's tail ending at months[upto_idx]."""
    window = months[max(0, upto_idx - tail): upto_idx + 1]
    sub = d[d["month"].isin(window)].sort_values("month")
    return sub["rs"].to_numpy(), sub["rs_mom"].to_numpy()


def rrg_interactive(panel, smooth=3, lookback=12, lag=3, tail=3):
    """Return an animated Plotly rotation graph (RS-Ratio x, RS-Momentum y).

    One animation frame per month. Each sector is a single dot coloured by the
    quadrant it occupies (the ticker label carries identity), with a short grey
    comet over the prior `tail` months; the slider and Play button carry the
    history, so no long trails accumulate on the chart. Quadrants are shaded for
    orientation. Axes are equal-aspect and symmetric about the origin, the
    neutral point.
    """
    out = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag)
    out = out.dropna(subset=["rs", "rs_mom"])
    sectors = sorted(out["category"].unique())
    months = sorted(out["month"].unique())
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()
    lim = float(np.nanmax(np.abs(out[["rs", "rs_mom"]].to_numpy()))) * 1.08 or 1.0

    def traces_for(month):
        idx = months.index(month)
        data = []
        for sec in sectors:
            d = out[out["category"] == sec]
            x, y = _sector_tail(d, idx, months, tail)
            if len(x):
                qname, c = QUADRANTS[(x[-1] >= 0, y[-1] >= 0)]
            else:
                qname, c = "", "#999999"
            data.append(go.Scatter(                      # grey comet
                x=x, y=y, mode="lines",
                line=dict(color="rgba(110,110,110,0.4)", width=1.5),
                showlegend=False, hoverinfo="skip"))
            data.append(go.Scatter(                      # quadrant-coloured head
                x=x[-1:], y=y[-1:], mode="markers+text",
                marker=dict(color=c, size=12, line=dict(color="white", width=1)),
                text=[ticker.get(sec, sec)] if len(x) else [],
                textposition="top center", textfont=dict(size=9, color="#444444"),
                showlegend=False,
                hovertemplate=(f"{sec} - {qname}<br>RS=%{{x:.2f}}"
                               f"<br>mom=%{{y:.2f}}<extra></extra>")))
        return data

    fig = go.Figure(
        data=traces_for(months[-1]),
        frames=[go.Frame(data=traces_for(m), name=str(pd.Timestamp(m).date()))
                for m in months],
    )

    # Shaded quadrants, drawn below the data, for at-a-glance orientation.
    for (pos_rs, pos_mom), (qname, c) in QUADRANTS.items():
        x0, y0 = (0 if pos_rs else -lim), (0 if pos_mom else -lim)
        fig.add_shape(type="rect", x0=x0, x1=x0 + lim, y0=y0, y1=y0 + lim,
                      fillcolor=_rgba(c, 0.06), line=dict(width=0), layer="below")
        fig.add_annotation(x=x0 + (lim if pos_rs else 0), y=y0 + (lim if pos_mom else 0),
                           text=qname, showarrow=False,
                           xanchor="right" if pos_rs else "left",
                           yanchor="top" if pos_mom else "bottom",
                           font=dict(color=c, size=12))
    fig.add_hline(y=0, line=dict(color="black", width=1))
    fig.add_vline(x=0, line=dict(color="black", width=1))

    steps = [dict(method="animate", label=f.name,
                  args=[[f.name], dict(mode="immediate",
                                       frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))])
             for f in fig.frames]
    fig.update_layout(
        title="Sector rotation, animated  (RS-Ratio vs RS-Momentum; latest month provisional)",
        xaxis=dict(title="RS-Ratio (standardized relative flow)", range=[-lim, lim], zeroline=False),
        yaxis=dict(title="RS-Momentum (3-month change)", range=[-lim, lim], zeroline=False,
                   scaleanchor="x", scaleratio=1),
        width=760, height=760, template="plotly_white", showlegend=False,
        sliders=[dict(active=len(steps) - 1, steps=steps, x=0, len=1.0,
                      currentvalue=dict(prefix="month: "))],
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.12,
                          buttons=[dict(label="Play", method="animate",
                                        args=[None, dict(fromcurrent=True,
                                                         frame=dict(duration=400, redraw=True),
                                                         transition=dict(duration=0))])])],
    )
    return fig


def quadrant_timeline_interactive(panel, smooth=3, lookback=12, lag=3):
    """Hoverable rotation timeline: sector x month grid coloured by quadrant.

    The interactive twin of viz.quadrant_timeline: each cell shows the quadrant
    the sector occupied that month, fading toward white when the point sits near
    the origin (weak signal). Hover any cell for the exact RS / momentum values.
    """
    rs, mom = _rrg_panel(panel, smooth, lookback, lag)
    RS, M = rs.to_numpy(dtype=float), mom.to_numpy(dtype=float)
    valid = ~(np.isnan(RS) | np.isnan(M))
    radius = np.hypot(RS, M)
    scale = float(np.nanpercentile(radius, 90)) or 1.0
    strength = np.clip(radius / scale, 0.0, 0.999)

    # z encodes quadrant + strength: the integer part picks the colour band, the
    # fractional part fades pale -> saturated within it. Quadratic in strength,
    # matching the static timeline, so weak months recede toward white.
    quads = list(QUADRANTS.items())
    code = np.full(RS.shape, np.nan)
    qname = np.full(RS.shape, "", dtype=object)
    for i, ((pos_rs, pos_mom), (name, _)) in enumerate(quads):
        m = valid & ((RS >= 0) == pos_rs) & ((M >= 0) == pos_mom)
        code[m] = i + strength[m] ** 2
        qname[m] = name
    colorscale = []
    for i, (_, (_, c)) in enumerate(quads):
        colorscale += [[i / 4, _pale(c)], [(i + 1) / 4, c]]

    # ISO strings, not Timestamps: every plotly JSON engine serializes them.
    months = [pd.Timestamp(c) for c in rs.columns]
    x = [m.date().isoformat() for m in months]
    # Plotly draws y bottom-up; flip so the strongest current sector is on top.
    fig = go.Figure(go.Heatmap(
        z=code[::-1], x=x, y=list(rs.index)[::-1],
        zmin=0.0, zmax=4.0, colorscale=colorscale,
        customdata=np.dstack([qname[::-1], RS[::-1], M[::-1]]),
        hoverongaps=False, xgap=1, ygap=1,
        colorbar=dict(tickvals=[0.5, 1.5, 2.5, 3.5],
                      ticktext=[name for _, (name, _) in quads],
                      len=0.7, thickness=12, outlinewidth=0),
        hovertemplate=("%{y} | %{x|%b %Y}: %{customdata[0]}"
                       "<br>RS=%{customdata[1]:.2f}, mom=%{customdata[2]:.2f}"
                       "<extra></extra>")))
    if len(months) >= 2:                                 # provisional fence
        fence = months[-2] + (months[-1] - months[-2]) / 2
        fig.add_vline(x=fence.isoformat(),
                      line=dict(color="black", width=1, dash="dash"))
    fig.update_layout(
        title="Sector rotation timeline  (pale = weak signal; last month provisional)",
        width=980, height=430, template="plotly_white",
        margin=dict(l=40, r=20, t=60, b=40))
    return fig


_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Fund-Flow Rotation Map</title></head>
<body style="font-family:-apple-system,'Segoe UI',sans-serif;max-width:1000px;margin:2em auto;color:#222222">
<h2 style="margin-bottom:0.2em">Fund-flow sector rotation</h2>
<p style="margin-top:0">Monthly fund flows across the eleven US equity sectors, reconstructed
from SEC N-PORT filings. Source and methodology:
<a href="https://github.com/mvpitr/fund-flow-rotation">github.com/mvpitr/fund-flow-rotation</a>.</p>
<p>Each dot is a sector, coloured by the rotation quadrant it currently occupies; the grey
comet trails the prior three months. Press Play or scrub the slider to watch the rotation.</p>
{rrg}
<p>The same rotation as a timeline: one strip per sector, coloured by the quadrant occupied
each month, pale when the signal is weak. Hover any cell for exact values.</p>
{timeline}
</body></html>
"""


def _write(db_path=DB_PATH, out_dir=FIG_DIR):
    import os
    os.makedirs(out_dir, exist_ok=True)
    panel = _load(db_path)
    # Fixed div ids so identical data yields byte-identical HTML (Plotly otherwise
    # stamps a random id), letting deploy.sh skip no-op publishes.
    html = _PAGE.format(
        rrg=rrg_interactive(panel).to_html(
            full_html=False, include_plotlyjs="cdn", div_id="rrg"),
        timeline=quadrant_timeline_interactive(panel).to_html(
            full_html=False, include_plotlyjs=False, div_id="timeline"))
    path = os.path.join(out_dir, "rrg_interactive.html")
    with open(path, "w") as f:
        f.write(html)
    print(f"saved -> {path}")


if __name__ == "__main__":
    _write()
