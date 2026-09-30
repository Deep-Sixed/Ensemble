from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Canonical install location location.
_DEFAULT_REPO_ROOT = Path("/opt/ensemble")
_DEFAULT_WORKSPACE = Path("/opt/workspace")


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """Return the Ensemble repository root."""
    override = os.getenv("ENSEMBLE_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    # src/ensemble/paths.py -> repo root
    inferred = Path(__file__).resolve().parents[2]
    if (inferred / "pyproject.toml").is_file():
        return inferred
    return _DEFAULT_REPO_ROOT


def models_dir() -> Path:
    override = os.getenv("ENSEMBLE_HOST_MODEL_DIR")
    if override:
        return Path(override).expanduser()
    return repo_root() / "models"


def default_workspace() -> Path:
    override = os.getenv("ENSEMBLE_WORKSPACE")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_WORKSPACE
