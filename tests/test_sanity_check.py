"""Offline tests for sanity_check helpers.

No network: only the pure date-window logic is exercised here; the checks
themselves need the real panel and price history.
"""

import pandas as pd

from sanity_check import _price_window


def test_price_window_tracks_panel_range():
    """Regression: the price window was hardcoded (end="2026-05-01"), so the
    return cross-check silently stopped covering months past April 2026. It
    must follow the panel: one bar before the first month (its pct_change
    return needs a prior bar) and an exclusive end one month past the last."""
    months = pd.Series(pd.to_datetime(["2019-06-30", "2024-01-31", "2026-04-30"]))
    start, end = _price_window(months)
    assert start == pd.Timestamp("2019-05-01")
    assert end == pd.Timestamp("2026-05-01")
