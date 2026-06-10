#!/usr/bin/env bash
# Build the web frontend and publish it to GitHub Pages.
#
# Bakes the panel into web/src/data.json, builds the Vite bundle, then publishes
# web/dist in a throwaway clone, so the current working tree and the main branch
# are never touched. Run from anywhere:  ./deploy.sh
#
# Live site: https://mvpitr.github.io/fund-flow-rotation/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"

echo "Exporting panel data..."
"$PY" "$ROOT/export_web_data.py"

echo "Building web bundle..."
(cd "$ROOT/web" && npm install --no-fund --no-audit --silent && npm run build --silent)
DIST="$ROOT/web/dist"
[ -f "$DIST/index.html" ] || { echo "error: $DIST was not produced"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
REMOTE="$(git -C "$ROOT" remote get-url origin)"

echo "Publishing to gh-pages..."
if git clone -q --branch gh-pages "$REMOTE" "$TMP" 2>/dev/null; then
  :                                   # existing gh-pages branch
else
  git clone -q "$REMOTE" "$TMP"       # first deploy: create the orphan branch
  git -C "$TMP" checkout -q --orphan gh-pages
  git -C "$TMP" rm -rq -r . >/dev/null 2>&1 || true
fi

find "$TMP" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$DIST/." "$TMP/"
git -C "$TMP" add -A
if git -C "$TMP" diff --cached --quiet; then
  echo "No change since last deploy; nothing to publish."
  exit 0
fi
git -C "$TMP" commit -q -m "Update rotation site ($(date +%Y-%m-%d))"
git -C "$TMP" push -q origin gh-pages
echo "Deployed -> https://mvpitr.github.io/fund-flow-rotation/"
