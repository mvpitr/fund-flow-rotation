#!/usr/bin/env bash
# Regenerate the interactive rotation graph and publish it to GitHub Pages.
#
# Publishing happens in a throwaway clone, so the current working tree and the
# main branch are never touched. Run from anywhere:  ./deploy.sh
#
# Live site: https://mvpitr.github.io/fund-flow-rotation/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-$ROOT/.venv/bin/python}"
SRC="$ROOT/docs/figures/rrg_interactive.html"

echo "Regenerating interactive RRG..."
"$PY" "$ROOT/viz_interactive.py"
[ -f "$SRC" ] || { echo "error: $SRC was not produced"; exit 1; }

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

cp "$SRC" "$TMP/index.html"
git -C "$TMP" add index.html
if git -C "$TMP" diff --cached --quiet; then
  echo "No change since last deploy; nothing to publish."
  exit 0
fi
git -C "$TMP" commit -q -m "Update interactive rotation graph ($(date +%Y-%m-%d))"
git -C "$TMP" push -q origin gh-pages
echo "Deployed -> https://mvpitr.github.io/fund-flow-rotation/"
