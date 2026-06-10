"""Offline smoke tests for the interactive Plotly rotation graph.

Verifies the animated figure builds from a synthetic panel with the expected
structure (frames, traces, equal-aspect axes) and round-trips to self-contained
HTML. No browser or network needed. Run with `pytest` from the repo root.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from viz_interactive import rrg_interactive, rrg_small_multiples_interactive


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


def test_rrg_small_multiples_interactive_builds():
    fig = rrg_small_multiples_interactive(_panel(), smooth=1, lookback=3, lag=1, tail=4)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 3                          # at least one trace per sector
    assert any(s.type == "rect" for s in fig.layout.shapes)   # quadrant shading
