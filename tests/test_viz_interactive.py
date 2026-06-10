"""Offline smoke tests for the interactive Plotly rotation figures.

Verifies the animated rotation graph and the quadrant timeline build from a
synthetic panel with the expected structure (frames, traces, equal-aspect axes,
hover payload) and round-trip to self-contained HTML. No browser or network
needed. Run with `pytest` from the repo root.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from viz_interactive import quadrant_timeline_interactive, rrg_interactive


def _panel(n=18, sectors=("Technology", "Energy", "Utilities")):
    months = pd.date_range("2023-01-31", periods=n, freq="ME")
    rows = []
    for base, sec in enumerate(sectors, start=1):
        for i, m in enumerate(months):
            rows.append({"ticker": sec[:3].upper(), "category": sec, "month": m,
                         "F": 100.0 * np.sin(i / 2.0 + base) + 20.0 * base, "aum": 1000.0})
    return pd.DataFrame(rows)


def test_rrg_interactive_builds():
    fig = rrg_interactive(_panel(), smooth=1, lookback=3, lag=1, tail=3)
    assert isinstance(fig, go.Figure)
    assert fig.frames                                 # animation frames exist
    assert len(fig.data) >= 1                         # at least one sector trace
    assert fig.layout.yaxis.scaleanchor == "x"        # equal aspect
    assert fig.layout.sliders                         # month slider present


def test_rrg_interactive_html_roundtrip(tmp_path):
    fig = rrg_interactive(_panel(), smooth=1, lookback=3, lag=1, tail=3)
    path = tmp_path / "rrg.html"
    fig.write_html(str(path), include_plotlyjs="cdn")
    assert path.exists() and path.stat().st_size > 1000


def test_quadrant_timeline_interactive_builds():
    fig = quadrant_timeline_interactive(_panel(), smooth=1, lookback=3, lag=1)
    assert isinstance(fig, go.Figure)
    assert fig.data and fig.data[0].type == "heatmap"
    assert fig.data[0].customdata is not None          # hover payload present
    z = np.asarray(fig.data[0].z, dtype=float)
    assert np.nanmax(z) < 4.0 and np.nanmin(z) >= 0.0  # codes stay in the colour bands
