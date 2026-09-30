#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ENSEMBLE_ROOT:-/opt/ensemble}"

cd "$ROOT_DIR"

if ! command -v code-review-graph >/dev/null 2>&1; then
  echo "error: code-review-graph is not installed" >&2
  echo "install with: pipx install code-review-graph" >&2
  exit 127
fi

echo "[ensemble] Building code-review-graph for: $ROOT_DIR"
code-review-graph build
code-review-graph status
