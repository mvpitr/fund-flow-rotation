"""Offline smoke tests for the matplotlib figures.

Pixels can't be asserted, but we can verify each figure builds from a synthetic
panel without raising or producing a degenerate (artless) axis. The Agg backend
keeps this headless. Run with `pytest` from the repo root.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

from viz import flow_heatmap, cumulative_flow_chart, rrg_plot


def _panel(n_months=18, sectors=("Technology", "Energy", "Utilities")):
    """A deterministic multi-sector panel with enough months to fill the windows."""
    months = pd.date_range("2023-01-31", periods=n_months, freq="ME")
    rows = []
    for base, sec in enumerate(sectors, start=1):
        for i, m in enumerate(months):
            rows.append({
                "ticker": sec[:3].upper(),
                "category": sec,
                "month": m,
                "F": 100.0 * np.sin(i / 2.0 + base) + 20.0 * base,   # varies, no flat sigma
                "aum": 1000.0,
            })
    return pd.DataFrame(rows)


def test_flow_heatmap_builds():
    fig = flow_heatmap(_panel(), lookback=3)
    assert isinstance(fig, Figure)
    assert fig.axes and fig.axes[0].images        # an actual heatmap image exists
    plt.close(fig)


def test_cumulative_flow_chart_builds():
    fig = cumulative_flow_chart(_panel(), window=3)
    assert isinstance(fig, Figure)
    assert any(ax.lines for ax in fig.axes)       # at least one sector line drawn
    plt.close(fig)


def test_rrg_plot_builds_with_points():
    fig = rrg_plot(_panel(20), lookback=3, lag=1, tail=3)
    assert isinstance(fig, Figure)
    assert fig.axes[0].lines                      # tails / markers present
    plt.close(fig)
