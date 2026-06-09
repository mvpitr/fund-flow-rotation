# Fund-Flow Rotation Map

**Where is investor capital actually moving — and what is it rotating *into*?**

This project reconstructs the flow of money across the US equity market, sector by
sector, and turns it into a rotation map: a view of which parts of the market are
attracting fresh capital and which are bleeding it, month over month. It is a
from-scratch rebuild of the kind of fund-flow and positioning signal that institutional
desks pay for — built entirely on free, public regulatory data.

## The idea: flows, not prices

A fund's assets under management move for two completely different reasons: the market
re-pricing what it already holds, and investors putting money in or taking it out.
Only the second is a **flow** — net new investor money, stripped of performance.

That distinction is the whole point. A sector can rise in price while investors quietly
pull money out, or fall while money pours in. Price tells you what happened; flow tells
you what investors *chose* — a cleaner read on conviction and rotation.

For an exchange-traded fund this is observable: shares are created when demand comes in
and redeemed when it leaves, so the net dollar creation/redemption is the flow. Funds
report exactly this each month. Normalizing by fund size gives a comparable growth rate:

```
F   = net new money         (dollar flow)
g   = F / AUM_at_start       (organic growth rate, comparable across funds)
```

Aggregate across funds, standardize against each sector's own history, and compare each
sector to the market as a whole, and the result is a **rotation map**.

## What it shows

The working panel covers the eleven sectors of the US equity market with ~7 years of
monthly history. From it, two views fall out immediately:

- **The snapshot** — net flow into and out of each sector this month.
- **The trend** — trailing cumulative flow, which sector is winning or losing capital
  over a window.

For example, a recent reading shows capital rotating out of the prior growth leadership
(Technology, Communication Services, Financials) and into Energy, defensives (Utilities,
Health Care) and Industrials — a classic late-cycle pattern, visible in *demand* well
before it shows up as a narrative. The planned visual layer renders this as a flow
heatmap and a Relative Rotation Graph (RRG) tracing each sector's path through the
lead / lag / improve / weaken quadrants over time.

## How it works

```
SEC fund filings  ->  monthly reported flows, returns, net assets, per fund
        ->  normalize to a comparable growth rate g and a clean monthly AUM series
        ->  aggregate to sectors; compare each sector to the whole-market flow
        ->  standardize (z-scores), measure momentum, plot rotation
```

- **Universe** — the eleven Select Sector SPDR ETFs, one per GICS sector, which together
  tile the entire US equity market.
- **Source** — SEC Form N-PORT, the monthly portfolio report every fund files. It
  discloses reported share creations/redemptions, total return, and net assets, so flows
  are read directly from the regulator rather than estimated.
- **Storage** — a tidy monthly panel persisted to SQLite, keyed on (ticker, month) so
  new filings accrue incrementally over time.
- **Validation** — reported returns are cross-checked against price-derived returns
  (correlation 0.99+), and the flow/return/AUM figures are checked for mutual consistency
  to within ~1% per quarter. See [`docs/fund-flow-rotation.tex`](docs/fund-flow-rotation.tex).

## Build status

| Phase | Status | |
|-------|--------|---|
| 1 | done | Single-fund flow engine and normalization |
| 2 | done | Multi-sector universe, classification, persisted monthly panel |
| 3 | next | Category flows and trailing cumulative windows |
| 4 | planned | Rotation metrics: relative flow, z-scores, momentum |
| 5 | planned | Visualization: flow heatmap and Relative Rotation Graph |

## Repo layout

```
nport_flows.py        Read monthly reported flows from SEC filings (single + multi-fund)
universe.csv          Classification map: ticker -> sector -> SEC series id
build_universe.py     Build the multi-sector monthly panel and persist to SQLite
sanity_check.py       End-to-end validation of the panel and current rotation output
phase1_xlk_flow.py    Single-fund flow math reference
docs/fund-flow-rotation.tex  Canonical methodology paper: full math, derivations, validation (compile with tectonic)
```

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Build the 11-sector monthly flow panel into data/flows.db
# (SEC asks API users to identify themselves with a name + email)
EDGAR_IDENTITY="Your Name your@email.com" python build_universe.py

# Validate the panel and print the current rotation snapshot
python sanity_check.py
```

## Scope and honesty

ETFs are a large but partial slice of all invested capital, and reported data carries a
modest lag. This is a deliberately transparent proxy for institutional positioning data,
not a replacement for it — the methodology paper is explicit about every assumption,
approximation, and limitation behind the numbers.
