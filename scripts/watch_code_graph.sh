#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${LOCAL_FIRST_ROOT:-/home/jarvis/local-first}"

cd "$ROOT_DIR"

if ! command -v code-review-graph >/dev/null 2>&1; then
  echo "error: code-review-graph is not installed" >&2
  echo "install with: pipx install code-review-graph" >&2
  exit 127
fi

echo "[local-first] Watching repo for code-review-graph updates: $ROOT_DIR"
code-review-graph watch
