# Fund-Flow Rotation Map - Working Rules

Reconstructs monthly fund flows across US equity sectors from SEC filings and turns
them into a rotation map. Small, honest, free-data portfolio project.

## Source of truth

`docs/methodology.md` is the spec. Whenever the approach, data source, a formula, or
the phase plan changes, update the methodology in the same pass - do not let it drift
from the code.

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
- `sanity_check.py` - end-to-end validation and current rotation output.
- `phase1_xlk_flow.py` - single-fund shares-based flow reference.
