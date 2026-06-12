"""Offline tests for the web-data exporter (export_web_data.build_payload)."""

import json

import numpy as np
import pandas as pd

from export_web_data import build_payload


def _panel(n_months=20, sectors=("Technology", "Energy", "Utilities")):
    months = pd.date_range("2023-01-31", periods=n_months, freq="ME")
    rows = []
    for base, sec in enumerate(sectors, start=1):
        for i, m in enumerate(months):
            rows.append({"ticker": sec[:3].upper(), "category": sec, "month": m,
                         "F": 100.0 * np.sin(i / 2.0 + base) + 20.0 * base, "aum": 1000.0})
    return pd.DataFrame(rows)


def test_payload_shape_and_alignment():
    p = build_payload(_panel(), smooth=1, lookback=3, lag=1, window=3)
    assert p["months"] and p["as_of"] == p["months"][-1]
    assert len(p["sectors"]) == 3
    for s in p["sectors"]:
        assert s["ticker"] and s["name"]
        for key in ("rs", "cf", "flow"):
            assert len(s[key]) == len(p["months"])   # series aligned to months


def test_payload_sorted_and_serializable():
    p = build_payload(_panel(), smooth=1, lookback=3, lag=1, window=3)
    latest = [s["rs"][-1] for s in p["sectors"]]
    assert all(v is not None for v in latest)        # every sector has a current rs
    assert latest == sorted(latest, reverse=True)    # strongest first (board order)
    json.dumps(p)                                    # round-trips to JSON


def test_payload_trims_warmup():
    p = build_payload(_panel(), smooth=1, lookback=3, lag=1, window=3)
    first = [s["rs"][0] for s in p["sectors"]]
    assert any(v is not None for v in first)         # no all-null leading months


def test_payload_turnover_block():
    p = build_payload(_panel(), smooth=1, lookback=3, lag=1, window=3)
    t = p["turnover"]
    assert len(t["months"]) == len(t["T"]) == len(t["tau"]) > 0
    assert t["months"] == sorted(t["months"])        # chronological
    assert all(v >= 0 for v in t["T"])               # gross turnover is non-negative
    assert all(0 <= v < 1 for v in t["tau"])
    # T needs only one month of prior assets, so its history starts no later
    # than the rs-trimmed month axis.
    assert t["months"][0] <= p["months"][0]
    json.dumps(p)                                    # round-trips to JSON
