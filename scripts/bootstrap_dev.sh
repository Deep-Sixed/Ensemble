#!/usr/bin/env bash
# Developer bootstrap: Python 3.14 venv, editable install, pytest smoke.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="${ENSEMBLE_PYTHON:-}"
if [[ -z "$PY" ]]; then
  for candidate in python3.14 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      major_minor="$("$candidate" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
      if [[ "$major_minor" == "3.14" ]]; then
        PY="$candidate"
        break
      fi
    fi
  done
fi

if [[ -z "$PY" ]]; then
  echo "error: Python 3.14 not found (set ENSEMBLE_PYTHON or install python3.14)" >&2
  exit 1
fi

py_patch="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")')"
if [[ "$py_patch" != "3.14.5" ]]; then
  echo "note: Python $py_patch detected; production target is 3.14.5 (temporary host lag is acceptable)"
fi

VENV="${ENSEMBLE_VENV:-$REPO_ROOT/.venv}"
recreate_venv=false
if [[ ! -x "$VENV/bin/python" ]]; then
  recreate_venv=true
elif ! "$VENV/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' >/dev/null 2>&1; then
  recreate_venv=true
elif [[ "$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "3.14" ]]; then
  recreate_venv=true
elif [[ -x "$VENV/bin/pip" ]] && head -1 "$VENV/bin/pip" | grep -q "$VENV" 2>/dev/null; then
  : # healthy venv
elif [[ -x "$VENV/bin/pip" ]] && ! "$VENV/bin/pip" --version >/dev/null 2>&1; then
  recreate_venv=true
fi

if [[ "$recreate_venv" == "true" ]]; then
  echo "creating $VENV"
  rm -rf "$VENV"
  "$PY" -m venv "$VENV"
fi

# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip setuptools wheel -q
python -m pip install -e ".[dev]"
python -m pip check

python -c "import ensemble; print('ensemble import ok:', ensemble.__file__)"
python -m pytest tests/ -q

echo "bootstrap complete: $VENV"
