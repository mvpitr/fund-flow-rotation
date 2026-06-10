# Fund-Flow Rotation Map - Working Rules

Reconstructs monthly fund flows across US equity sectors from SEC filings and turns
them into a rotation map. Small, honest, free-data portfolio project.

## Source of truth

`docs/fund-flow-rotation.tex` is the spec (the quant-protocol "clean paper", State 2;
compile with `tectonic docs/fund-flow-rotation.tex`). Whenever the approach, data source,
a formula, or the phase plan changes, update the paper in the same pass - do not let it
drift from the code. Every core equation carries a semantic `\label{eq:...}`, and the
math-implementing functions reference those labels via `@math_ref` (see below).

## Workflow

- When a change touches design, update the methodology first, then write code, then tests.
- Make minimal changes: fix the reported problem, not surrounding code.
- Solve the real problem, not the symptom - no workarounds that degrade correctness.
- Prefer existing libraries (edgartools, pandas, yfinance, stdlib sqlite3) over
  hand-rolling. Search before building anything non-trivial.

## Tests

- Run `pytest` from the repo root before considering anything done.
- Every feature gets a unit test; every bug gets a regression test (added with the fix).
- Unit tests are offline and deterministic (synthetic data) - no network.
- `sanity_check.py` is a separate, live end-to-end validation against the built panel;
  it is not a substitute for the unit tests.

## Traceability (theory <-> code)

- Every function implementing a formula from the paper carries `@math_ref eq:<label>`
  in its docstring, naming the equation it projects (e.g. `@math_ref eq:flow_split`).
- `tests/test_math_refs.py` enforces that every `@math_ref` resolves to a real
  `\label{eq:...}` in the paper; it runs with the suite. Pure infrastructure
  (I/O, persistence, plotting) does not need a `@math_ref`.

## Commits

- Commit small logical units; push to `origin main` after each. Do not let changes pile up.
- No emojis anywhere - chat, code, comments, docs, or commit messages.

## Data and running

- SEC EDGAR requires an identity: set `EDGAR_IDENTITY="Your Name your@email.com"`.
- Build the panel: `EDGAR_IDENTITY=... python build_universe.py` -> `data/flows.db`.
- Validate + see current output: `python sanity_check.py`.
- `data/` is gitignored (regenerable); `universe.csv` and code are tracked.

## Key modules

- `nport_flows.py` - read reported monthly flows from SEC N-PORT (single + multi-fund).
- `build_universe.py` - build and persist the monthly panel to SQLite.
- `categories.py` - aggregate per-fund flows to category flows, whole-market baseline, and trailing cumulative windows.
- `sanity_check.py` - end-to-end validation and current rotation output.
- `shares_flow.py` - shares-route daily flow reference (counterpart to the reported N-PORT route).
