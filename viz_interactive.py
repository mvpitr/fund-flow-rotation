"""Phase 5: interactive Plotly rotation graph (web showcase).

A Relative Rotation Graph with a month slider: scrub through time and watch each
sector trace its path through the leading / weakening / lagging / improving
quadrants. Reuses rrg_coordinates from rotation.py (the RS-Ratio / RS-Momentum
math lives there and in the paper), so this module is plotting only -- no
@math_ref. Sector legend entries toggle, so a cluttered all-sector view can be
thinned to the few sectors of interest.

The CLI writes a self-contained HTML file to docs/figures/rrg_interactive.html.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from categories import category_panel
from rotation import rrg_coordinates
from viz import DB_PATH, FIG_DIR, _load

# A distinct colour per sector (qualitative palette).
_PALETTE = px.colors.qualitative.Alphabet


def _sector_tail(d, upto_idx, months, tail):
    """Coordinates of one sector's tail ending at months[upto_idx]."""
    window = months[max(0, upto_idx - tail): upto_idx + 1]
    sub = d[d["month"].isin(window)].sort_values("month")
    return sub["rs"].to_numpy(), sub["rs_mom"].to_numpy()


def rrg_interactive(panel, smooth=3, lookback=12, lag=3, tail=6):
    """Return an animated Plotly rotation graph (RS-Ratio x, RS-Momentum y).

    Each animation frame is one month; per sector a lines+markers trace shows the
    trailing `tail`-month path, the final (current) marker enlarged. The slider and
    play button step through months. Axes are equal-aspect and symmetric about the
    origin so quadrant membership is not a scaling artifact.
    """
    out = rrg_coordinates(category_panel(panel), panel,
                          smooth=smooth, lookback=lookback, lag=lag)
    out = out.dropna(subset=["rs", "rs_mom"])
    sectors = sorted(out["category"].unique())
    months = sorted(out["month"].unique())
    # animate only months where at least one sector is defined
    anim = [m for m in months if (out["month"] == m).any()]
    lim = float(np.nanmax(np.abs(out[["rs", "rs_mom"]].to_numpy()))) * 1.1 or 1.0
    color = {sec: _PALETTE[i % len(_PALETTE)] for i, sec in enumerate(sectors)}

    def traces_for(month):
        idx = months.index(month)
        data = []
        for sec in sectors:
            d = out[out["category"] == sec]
            x, y = _sector_tail(d, idx, months, tail)
            sizes = [6] * len(x)
            if sizes:
                sizes[-1] = 14
            data.append(go.Scatter(
                x=x, y=y, name=sec, mode="lines+markers",
                line=dict(color=color[sec], width=1.5),
                marker=dict(color=color[sec], size=sizes),
                legendgroup=sec, hovertemplate=f"{sec}<br>RS=%{{x:.2f}}<br>mom=%{{y:.2f}}<extra></extra>",
            ))
        return data

    fig = go.Figure(
        data=traces_for(anim[-1]),
        frames=[go.Frame(data=traces_for(m), name=str(pd.Timestamp(m).date())) for m in anim],
    )

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
        width=760, height=760, template="plotly_white",
        sliders=[dict(active=len(steps) - 1, steps=steps, x=0, len=1.0,
                      currentvalue=dict(prefix="month: "))],
        updatemenus=[dict(type="buttons", showactive=False, x=0, y=-0.12,
                          buttons=[dict(label="Play", method="animate",
                                        args=[None, dict(fromcurrent=True,
                                                         frame=dict(duration=400, redraw=True),
                                                         transition=dict(duration=0))])])],
    )
    return fig


def _write(db_path=DB_PATH, out_dir=FIG_DIR):
    import os
    os.makedirs(out_dir, exist_ok=True)
    fig = rrg_interactive(_load(db_path))
    path = os.path.join(out_dir, "rrg_interactive.html")
    fig.write_html(path, include_plotlyjs="cdn")
    print(f"saved -> {path}")


if __name__ == "__main__":
    _write()
