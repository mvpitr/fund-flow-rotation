"""Export the rotation panel to static JSON for the web frontend (web/).

The web page is a pure projection: every number it shows is computed here, in
Python, by the same modules the figures and tests use -- rs from
rotation.rrg_coordinates (via viz._rrg_panel), dollar windows from
categories.cumulative_flow, turnover from rotation.rotation_turnover. The
exporter bakes them into web/src/data.json at build time, which is what lets
the deployed site stay a static page with no backend. Persistence only -- no
@math_ref.
"""

import json
import os

import pandas as pd

from categories import category_panel, cumulative_flow
from rotation import rotation_turnover
from viz import _load, _rrg_panel

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "web", "src", "data.json")


def _series(wide, row, ndigits):
    return [None if pd.isna(v) else round(float(v), ndigits) for v in wide.loc[row]]


def build_payload(panel, smooth=3, lookback=12, lag=3, window=6):
    """Aligned monthly series per sector, strongest current rs first.

    Months are trimmed to where rs exists (viz._rrg_panel); NaN becomes null.
    `lag` is shipped so the frontend can mark "lag months ago" without
    recomputing anything. The turnover block keeps its own (longer) month axis:
    T_t needs only one month of prior assets, so its history starts before the
    rs warmup window.
    """
    rs, _ = _rrg_panel(panel, smooth, lookback, lag)
    cp = category_panel(panel)
    cat = cumulative_flow(cp, window=window)
    cf = cat.pivot(index="category", columns="month", values=f"CF{window}").reindex(
        index=rs.index, columns=rs.columns)
    flow = cat.pivot(index="category", columns="month", values="F").reindex(
        index=rs.index, columns=rs.columns)
    ticker = panel.drop_duplicates("category").set_index("category")["ticker"].to_dict()

    months = [pd.Timestamp(m).date().isoformat() for m in rs.columns]
    sectors = [{
        "name": sec,
        "ticker": ticker.get(sec, sec),
        "rs": _series(rs, sec, 3),
        "cf": _series(cf, sec, 0),
        "flow": _series(flow, sec, 0),
    } for sec in rs.index]
    turn = rotation_turnover(cp, panel).dropna()
    turnover = {
        "months": [pd.Timestamp(m).date().isoformat() for m in turn["month"]],
        "T": [round(float(v)) for v in turn["T"]],
        "tau": [round(float(v), 4) for v in turn["tau"]],
    }
    return {"as_of": months[-1], "provisional": True, "window": window,
            "lag": lag, "months": months, "sectors": sectors,
            "turnover": turnover}


def _write(out_path=OUT_PATH):
    payload = build_payload(_load())
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(payload, f, separators=(",", ":"))
    print(f"saved -> {out_path}  ({len(payload['months'])} months, "
          f"{len(payload['sectors'])} sectors)")


if __name__ == "__main__":
    _write()
