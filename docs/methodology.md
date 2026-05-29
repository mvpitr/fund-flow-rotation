# Fund-Flow Rotation Map — Methodology & Math

A from-scratch reference for the project. No prior finance knowledge assumed.
Read top to bottom; each section builds on the previous one.

---

## 0. The one-sentence idea

> A **rotation map** shows where investor money is flowing *into* and *out of*,
> across categories (sectors, regions, asset classes), over time — revealing how
> capital "rotates" around the market and what investors are collectively betting on.

This is the heart of what EPFR sells. We will rebuild a small version of it from
free, public ETF data.

---

## 1. What is a "fund flow"? (the core concept)

A fund's size — its **AUM** (Assets Under Management) — changes for two completely
different reasons:

1. **Market moves.** The assets the fund already holds go up or down in price.
2. **Investor decisions.** People put *new* money in (inflow) or take money out
   (outflow).

A **flow** is reason (2) only — the net new money from investors, stripped of
market performance.

This distinction is the whole game. Consider:

```
A fund starts the day worth $100.
The market rises 2%, so its holdings are now worth $102 with no investor action.
At the close, the fund is worth $101.

AUM went UP (100 -> 101), but investors actually PULLED money out:
  expected from market alone = 102
  actual                     = 101
  flow                       = 101 - 102 = -1   (a $1 OUTFLOW)
```

**Key takeaway:** AUM rising does *not* mean money flowed in. Flow is a *demand*
signal (what investors chose to do), not a *price* signal. That's why it's an
independent, interesting measure of sentiment.

---

## 2. Measuring flows from public data

### 2a. The AUM identity (works for any fund)

Over one period `t`, AUM evolves as:

```
AUM_t = AUM_{t-1} * (1 + r_t) + F_t
```

- `AUM_t`    = assets under management at end of period t
- `r_t`      = the fund's total return over period t (price change + distributions)
- `F_t`      = net dollar flow over period t   <-- what we want

The first term is "what last period's money grew to on its own." Anything beyond
that must be new investor money. Rearranging:

```
F_t = AUM_t - AUM_{t-1} * (1 + r_t)
```

This is the **estimated net flow**. It's the general method and works for mutual
funds too.

### 2b. The ETF shortcut: shares outstanding

ETFs have a special mechanism that makes flows easy to see directly.

ETFs continuously **create** and **redeem** shares in response to demand: when
investors want in, "authorized participants" create new shares; when they want
out, shares are destroyed. So the number of shares in existence (`S_t`, "shares
outstanding") moves *with investor demand*. (Mutual funds don't publish this
cleanly; ETFs do, daily — that's why we start with ETFs.)

Each share created/redeemed is worth roughly one NAV (net asset value per share).
So:

```
F_t  ≈  (S_t - S_{t-1}) * NAV_t
```

- `S_t`    = shares outstanding at end of period t
- `NAV_t`  = net asset value per share at end of period t

### 2c. Why 2a and 2b are the *same thing* (short derivation)

`AUM_t = S_t * NAV_t`, and if we ignore distributions then
`r_t = NAV_t / NAV_{t-1} - 1`. Substitute into the AUM identity:

```
AUM_{t-1} * (1 + r_t) = (S_{t-1} * NAV_{t-1}) * (NAV_t / NAV_{t-1})
                      =  S_{t-1} * NAV_t

F_t = AUM_t - S_{t-1} * NAV_t
    = S_t * NAV_t - S_{t-1} * NAV_t
    = (S_t - S_{t-1}) * NAV_t          <-- the shares-outstanding formula
```

So the "change in shares × NAV" method is just the general flow formula applied to
an ETF. Reassuring, and it tells us exactly which assumptions we're making (mainly:
ignoring distributions, using end-of-period NAV).

### 2d. Conventions to pin down early

- **Which price?** Use **NAV** (not the market trading price) to value flows; ETFs
  trade at small premiums/discounts to NAV and we want the underlying asset value.
- **Timing:** we use end-of-period `NAV_t` to value the period's share change. This
  is the standard approximation.
- **Period length:** daily data is available but noisy; we'll often roll up to
  weekly. The math is identical, just a coarser `t`.

### Worked ETF example

```
S_{t-1} = 10.0M shares
S_t     = 10.2M shares
NAV_t   = $50

F_t = (10.2M - 10.0M) * 50 = 0.2M * 50 = $10M inflow
```

### 2e. Reading *reported* flows from Form N-PORT (our backfill source)

Methods 2a/2b *estimate* flow from things we can see (AUM, shares, NAV). But there
is a source where the fund reports its flow almost directly: the SEC's **Form
N-PORT**, which every US ETF and mutual fund files monthly. For each of the three
months in a reporting period it discloses:

- **Item B.8 — flow activity:** total `sales` (creations), `redemptions`, and
  `reinvestment` of fund shares, in dollars. Net flow is `F = sales − redemptions`
  (reinvestment is internal dividend recycling, ~0 for ETFs).
- **Item B.7 — monthly total return** (already includes distributions).
- **Item B.1 — net assets** (AUM) at the period end.

This sidesteps the no-free-ETF-shares problem entirely (§7): instead of inferring
`ΔS`, we read the regulator-collected flow. Trade-offs: **monthly** granularity and
a **~2-month reporting lag** (filings post ~60 days after quarter-end), vs. the
daily-but-blocked shares method. So N-PORT is our **historical backfill**; the
shares/AUM methods remain the path for daily, going-forward data.

**Two validations we actually ran (XLK, 81 months back to 2019-07):**

1. N-PORT's reported monthly total return vs. the price-derived monthly return
   matches to ~0.01–0.03 pp — confirming the data and the month-ordering.
2. Rolling the AUM identity (§2a) forward from a single early `net_assets` anchor
   re-hits later reported `net_assets` to within ~3.6% median over 27 quarter-end
   anchors — independent confirmation that flows and returns are mutually consistent.
   (Re-anchoring at each report would tighten this; we keep the single-anchor roll
   as an honest drift diagnostic.)

---

## 3. Normalizing flows

A $10M inflow is huge for a tiny fund and a rounding error for a giant one. To
compare funds, divide by starting size to get the **organic growth rate**:

```
g_t = F_t / AUM_{t-1}
```

In the example above, if `AUM_{t-1} = 10.0M * 50 = $500M`, then
`g_t = 10M / 500M = 2%`. "The fund grew 2% from new money this period."

Use **dollar flows** when you care about absolute capital moved (headlines: "$10B
into tech"); use **normalized flows `g`** when you compare categories of different
sizes. The rotation map mostly uses `g`.

---

## 4. Aggregating funds into categories

A single fund isn't a "sector." We group funds into categories `c` (e.g. *Tech*,
*Energy*, *Emerging Markets*, *US Treasuries*) and aggregate.

**Step 1 — classification.** Map each fund `i` to a category. (This is a real data
problem: from fund metadata / its benchmark. Start simple with a hand-curated list
of well-known sector & region ETFs.)

**Step 2 — aggregate within each category:**

```
Category dollar flow:     F_{c,t} = sum over i in c of  F_{i,t}
Category AUM:             A_{c,t} = sum over i in c of  AUM_{i,t}
Category normalized flow: g_{c,t} = F_{c,t} / A_{c,t-1}
```

Note `g_{c,t}` is an **AUM-weighted** average of member funds' flows (big funds
count more), which is usually what you want.

---

## 5. From flows to "rotation"

Raw `g_{c,t}` per category per period is the raw material. "Rotation" needs two
more ideas: **time smoothing**, **cross-category comparison**, and **momentum**.

### 5a. Time smoothing (kill the daily noise)

Cumulative flow over a trailing window of `W` periods:

```
CF_{c,t}(W) = sum over k = 0..W-1 of  F_{c,t-k}
```

Common windows: 4-week and 13-week cumulative flows. This is what reveals
sustained trends rather than one-day blips.

### 5b. Standardize for fair comparison (z-scores)

Different categories have different "normal" flow volatility, so raw `g` isn't
comparable across them. Standardize each category against its own recent history
(rolling lookback `L`):

```
z_{c,t} = (g_{c,t} - mean_L(g_c)) / std_L(g_c)
```

`z = +2` means "this category is getting unusually strong inflows vs. its own
norm." Z-scores are what make a clean, comparable **heatmap**.

### 5c. Relative flow (the "rotation" part)

Rotation is inherently *relative* — money leaving A to enter B. Compare each
category to the whole universe `U`:

```
g_{U,t}   = F_{U,t} / A_{U,t-1}            (whole-universe normalized flow)
rel_{c,t} = g_{c,t} - g_{U,t}              (excess flow vs. the market)
```

`rel > 0`: this category is attracting more than its share of capital.
`rel < 0`: capital is rotating away from it.

### 5d. Momentum

Is a category's relative strength *rising* or *fading*? Measure the change:

```
m_{c,t} = rel_{c,t} - rel_{c,t-D}          (change over D periods)
```

### 5e. The rotation quadrants (the conceptual destination)

Plot each category by (relative strength `rel`, momentum `m`). This is modeled on
**Relative Rotation Graphs (RRG)**. Four quadrants describe the lifecycle of a
rotation:

```
                momentum m
                    ^
      IMPROVING     |     LEADING
   (weak, rising)   |  (strong, rising)
   --------------------------------------> relative strength rel
      LAGGING       |     WEAKENING
  (weak, falling)   |  (strong, falling)
```

A category typically circles clockwise: Improving -> Leading -> Weakening ->
Lagging -> Improving. Watching categories travel around this map *is* the rotation
story.

---

## 6. Turning the math into pictures

- **Heatmap** — rows = categories, columns = time, color = `z_{c,t}` (or `g`).
  Diverging colormap (blue = outflow, red = inflow). The flagship view.
- **Latest-period bar chart** — `F_{c,t}` or `g_{c,t}` by category, sorted. "Where
  did money go this week."
- **Cumulative-flow lines** — `CF_{c,t}(W)` per category over time.
- **RRG scatter** — x = `rel`, y = `m`, with a short trailing tail per category so
  you can see the rotation direction.

---

## 7. Data realities & gotchas (where projects quietly break)

- **Share splits.** A 2:1 ETF split doubles `S` overnight with *zero* flow. Naive
  `ΔS` shows a fake giant inflow. Detect/adjust using split-adjusted shares or by
  flagging implausible one-day jumps.
- **Distributions / dividends.** On an ex-dividend date NAV drops by the payout. If
  `r_t` doesn't include the distribution, flow is mismeasured. Use total-return NAV
  or handle distribution dates explicitly.
- **Survivorship.** Funds launch and close. Only include a fund in periods where it
  actually existed, or you'll bias the history.
- **Multiple share classes** (mostly mutual funds). Aggregate classes up to the
  fund before categorizing.
- **Currency.** Foreign-listed funds report in local currency; convert to a common
  base (USD) before summing.
- **NAV vs. market price.** Value flows at NAV; the trading price includes a
  premium/discount we don't want.
- **Reporting lag.** Shares-outstanding figures often post T+1; don't treat today's
  number as final.
- **Yahoo has no ETF shares time series (the big one).** `yfinance.get_shares_full()`
  returns a daily shares-outstanding series for *stocks* (e.g. AAPL) but comes back
  **empty for ETFs** (verified for XLK, SPY, QQQ, XLE on 2026-05-29). Yahoo exposes
  only a single current `sharesOutstanding` point for ETFs — and it can be stale or
  split-confused. Since ΔS for ETFs is our core primitive, Phase 1's data path needs
  a different source (issuer files, a fundamentals API, or snapshotting forward). Note
  also that free vendors disagree materially on the *level*: on 2026-05-29 Yahoo put
  XLK at 272M shares / $103B, stockanalysis.com at 651M / $122B, and FMP at 544M.
  FMP's `/stable/shares-float` *does* cover ETFs (a `fetch_shares_fmp` hook exists),
  but its FREE tier returns only the **current** snapshot — the historical-shares /
  historical-market-cap endpoints are premium. So free APIs enable a snapshot-forward
  series, not a backfill; real daily history needs a paid tier or issuer files.
  **Resolution:** for free historical backfill we read *reported* monthly flows from
  Form N-PORT instead (§2e); the shares methods stay the daily/forward path.
- **Representativeness caveat.** ETFs are a large but *partial* slice of all
  investor money (EPFR also covers mutual funds, which are bigger in some markets).
  Our ETF-only map is a strong proxy, not the whole truth — worth stating openly.

---

## 8. Notation glossary

```
t          time period index (day or week)
i          a single fund
c          a category (sector / region / asset class)
U          the whole universe of funds
S_t        shares outstanding at end of t
NAV_t      net asset value per share at end of t
AUM_t      assets under management = S_t * NAV_t
r_t        fund total return over period t
F_t        net dollar flow over period t
g_t        normalized flow (organic growth) = F_t / AUM_{t-1}
F_{c,t}    category dollar flow
g_{c,t}    category normalized flow
CF(W)      trailing cumulative flow over W periods
z_{c,t}    z-score of g_{c,t} over rolling lookback L
rel_{c,t}  relative flow = g_{c,t} - g_{U,t}
m_{c,t}    flow momentum = rel_{c,t} - rel_{c,t-D}
```

---

## 9. How the math maps to build phases (iterative roadmap)

Each phase is a small, working, demoable artifact. We do them in order.

| Phase | What we build | Math used |
|-------|---------------|-----------|
| 1 ✅ | Flow for **one** ETF: split-aware `F_t`, `g_t`. Free ETF shares turned out to be blocked (§7), so real history comes from N-PORT reported flows (§2e) — 81 months of XLK, returns cross-checked. | §2, §3 |
| 2 done | **Many** ETFs + classification + persistence. Universe = the 11 Select Sector SPDRs (one fund per GICS sector); all live in one SEC trust so a single N-PORT pass covers them. Stored as a monthly panel in SQLite (`data/flows.db`), keyed on (ticker, month) for incremental updates. 891 rows back to 2019-07. | §2e, §4 |
| 3 | **Category** flows: `F_{c,t}`, `g_{c,t}`, cumulative windows. | §4, §5a |
| 4 | **Rotation metrics**: z-scores, relative flow, momentum, quadrants. | §5b–§5e |
| 5 | **Visualize**: heatmap + RRG. | §6 |

Phases 1-2 are complete (real N-PORT history, 11-sector SQLite panel); next is Phase 3.

**Note on the starting universe.** Because the Phase 2 universe has exactly one fund
per category (sector ETF = sector), the §4 within-category aggregation is currently an
identity (`F_{c,t} = F_{i,t}`). That is fine: it means the *cross-category* rotation
(relative flow across the 11 sectors, §5c) is immediately reachable. The aggregation
machinery only starts doing real work once a category holds multiple funds.
