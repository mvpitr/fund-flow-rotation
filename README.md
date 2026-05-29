# Fund-Flow Rotation Map

A from-scratch, EPFR-inspired **fund-flow rotation map** built from free, public ETF
data. The goal is to reconstruct where investor capital is flowing — into and out of
sectors, regions, and asset classes — and visualize how it *rotates* around the market
over time.

> A rotation map reveals what investors are collectively betting on by separating
> genuine *flows* (new investor money) from mere *price moves*. See
> [`docs/methodology.md`](docs/methodology.md) for the full math and reasoning.

## Why

This is an intellectual portfolio project: rebuild a small, honest version of the kind
of fund-flows / positioning product that data vendors like EPFR sell, using only free
data (ETF shares outstanding + prices via `yfinance`).

## The core idea

A fund's AUM changes for two reasons: the market moving, and investors adding/removing
money. A **flow** is the second part only. For ETFs we can read it almost directly from
the change in shares outstanding:

```
F_t ≈ (S_t − S_{t−1}) · NAV_t
```

Aggregate flows into categories, normalize, smooth, and standardize, and you get a
comparable **rotation map** (heatmap + Relative Rotation Graph).

## Roadmap

The build is iterative — each phase is a small, working artifact:

| Phase | Status | What we build |
|-------|--------|---------------|
| **1** | done | Flow for **one** ETF (XLK): split-aware `F_t`, `g_t`. Free ETF shares are blocked (see below), so real history comes from **SEC N-PORT** reported flows — 81 months of XLK, returns cross-checked against prices. |
| **2** | done | **Many** ETFs + a classification map; persist time series. Built for the 11 Select Sector SPDRs (one fund per sector) into a SQLite panel — 891 monthly rows back to 2019. |
| 3 | next | **Category** flows and cumulative windows. |
| 4 | | **Rotation metrics**: z-scores, relative flow, momentum, quadrants. |
| 5 | | **Visualize**: heatmap + RRG. |

Currently at the end of Phase 2: a monthly flow panel for the 11 US equity sectors.

## Layout

```
phase1_xlk_flow.py    Phase 1: daily flow math for a single ETF (shares-based; needs a shares feed)
nport_flows.py        Monthly REPORTED flows from SEC N-PORT (works today, free); single + multi-fund fetch
universe.csv          Phase 2: the classification map (ticker -> category -> SEC series id)
build_universe.py     Phase 2: build the multi-ETF monthly flow panel and persist to SQLite
docs/methodology.md   Full methodology, math, and data gotchas
requirements.txt      Python dependencies
```

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build the full 11-sector monthly flow panel into data/flows.db (SEC needs an identity):
EDGAR_IDENTITY="Your Name your@email.com" python build_universe.py

# Single-ETF N-PORT report (defaults to XLK):
EDGAR_IDENTITY="Your Name your@email.com" python nport_flows.py

# Shares-based daily flow math (FMP_API_KEY optional; Yahoo has no ETF shares):
python phase1_xlk_flow.py
```

## Caveats

ETFs are a large but *partial* slice of all investor money, and free data has reporting
lags, splits, and distributions to handle carefully (see methodology §7). This is a
strong proxy, not the whole truth — stated openly by design.

**Known data gap:** Yahoo's `get_shares_full()` returns empty for ETFs (it only works
for stocks), so the live shares-outstanding series — our core input — isn't available
from `yfinance` alone. The flow math is implemented and split-aware; sourcing ETF
shares from an issuer/fundamentals feed is the open task. See methodology §7.
