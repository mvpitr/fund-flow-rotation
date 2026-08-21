# Fund-Flow Rotation Map

**Where is investor capital actually moving — and what is it rotating *into*?**

**Live demo:** [fund-flow rotation site](https://mvpitr.github.io/fund-flow-rotation/) —
a flow leadership board (which sectors were gaining or losing investor money as of
March 2026, with the three-month trend) and a five-year rotation strip, one row per
sector. (N-PORT data posts roughly 60 days after each fiscal quarter end, so the board
reports a closed month, not the current one.)

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
monthly history. From it, three views fall out:

- **The snapshot** — net flow into and out of each sector this month.
- **The trend** — trailing cumulative flow, which sector is winning or losing capital
  over a window.
- **The rotation map** — each sector's flow relative to the whole-market tide,
  standardized against its own history, and the momentum of that relative strength —
  placing each sector in a lead / lag / improve / weaken quadrant.
- **The intensity** — gross rotation turnover: the dollars that changed sectors each
  month. Above- and below-market flows cancel exactly across sectors, so the matched
  size of the two sides measures how violent the rotation is, whoever wins it.

As an illustration of what the map surfaces: in the March 2026 panel, the standardized
relative-flow ranking runs from Energy (+3.3σ), Materials (+1.2σ) and Industrials
(+0.6σ) at the top down to Communication Services (−4.6σ), Consumer Discretionary
(−1.7σ) and Technology (−1.5σ) at the bottom. That is a description of where reported
money went over the smoothing window — an ordering to look at, not a forecast, a regime
call, or a claim about what caused it.

The visual layer exists in two parts. `python viz.py` renders static figures into
`docs/figures/`: a flow heatmap, a Relative Rotation Graph (RRG) placing each sector in
the lead / lag / improve / weaken quadrants, a per-sector small-multiples version of the
same, a quadrant timeline, and a cumulative-flow chart. The live site is a separate and
narrower view — leadership board, rotation strip, turnover strip — and does **not**
render the RRG; that chart is currently static-figure only.

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

## Repo layout

```
nport_flows.py        Read monthly reported flows from SEC filings (single + multi-fund)
universe.csv          Classification map: ticker -> sector -> SEC series id
build_universe.py     Build the multi-sector monthly panel and persist to SQLite
categories.py         Aggregate per-fund flows to category flows, g_U, and CF(W) windows
rotation.py           Rotation stats: relative flow, z-score, momentum, RRG coordinates
viz.py                Static figures: rotation snapshot, rotation timeline, strength heatmap, cumulative flow, small multiples
export_web_data.py    Bake the panel into web/src/data.json for the frontend (all math stays in Python)
web/                  React + TypeScript + Vite frontend: SVG leadership board + ECharts rotation strip
sanity_check.py       End-to-end validation of the panel and current rotation output
shares_flow.py        Shares-route daily flow reference (eq:flow_shares, eq:flow_split)
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

# Render the static figures into docs/figures/
python viz.py

# Build the web frontend (bakes web/src/data.json from the panel first)
python export_web_data.py
cd web && npm install && npm run dev    # or: npm run build; ./deploy.sh publishes
```

## Automated refresh

A scheduled GitHub Actions workflow (`.github/workflows/refresh.yml`) keeps the live
site current without manual deploys — the CI twin of `./deploy.sh`. On the 5th of every
month (and on demand via workflow_dispatch) it:

1. rebuilds `data/flows.db` from EDGAR (`build_universe.py`, identity from the
   `EDGAR_IDENTITY` repo secret),
2. runs the test suite (`pytest`) as a hard gate,
3. runs `sanity_check.py` for the audit log (informational only — its yfinance
   cross-check is unreliable from CI network addresses),
4. bakes `web/src/data.json`, builds the Vite bundle, and publishes `web/dist` to the
   `gh-pages` branch.

New N-PORT filings post in quarterly waves (public ~60 days after each fiscal quarter
end), so roughly every third run picks up three new months; when nothing changed, the
publish step detects an identical bundle and deploys nothing.

## Scope and honesty

ETFs are a large but partial slice of all invested capital. This is a deliberately
transparent proxy for institutional positioning data, not a replacement for it — the
methodology paper is explicit about every assumption, approximation, and limitation
behind the numbers. The specific limitations a reader should hold onto:

- **Single fund family.** The universe is one issuer's sector ETFs — the eleven Select
  Sector SPDRs — and nothing else. A dollar leaving XLK for a competing technology ETF
  reads here as a technology outflow, when it is a vehicle switch rather than a change
  of view on the sector.

- **Standardization sample.** The panel holds 81 monthly observations per sector
  (July 2019 through March 2026), and each z-score standardizes against only the twelve
  months immediately prior to it. A history this short is sensitive to the regimes
  inside it: the 2020 flow shock sits in the sample, and sits inside the standardization
  window itself for roughly the first year of usable output.

- **No predictive claim.** The map measures realized flow — money that has already
  moved. It has never been tested against forward returns; there is no backtest, no
  information coefficient, no hit rate anywhere in this repo. Nothing here should be
  read as a return signal.

- **Reporting lag.** N-PORT filings become public roughly 60 days after each fiscal
  quarter end, and they arrive in quarterly waves — three new months land at once,
  rather than one arriving each month. The panel therefore trails the calendar by
  between two and five months depending on where in the cycle you look: it ends at
  March 2026 as of August 2026, with April through June due when the June-quarter wave
  posts around the end of August.
