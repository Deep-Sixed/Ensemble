from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_WORKSPACE = Path("/home/jarvis/projects/nexus")


def default_workspace() -> Path:
    override = os.getenv("ENSEMBLE_WORKSPACE")
    if override:
        return Path(override).expanduser()
    return _DEFAULT_WORKSPACE
