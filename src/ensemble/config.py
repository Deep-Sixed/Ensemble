from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ensemble.paths import default_workspace


@dataclass(frozen=True)
class EnsembleConfig:
    workspace: Path
    max_file_bytes: int
    checkpoint_dir: Path
    context_token_budget: int


# Checkout root for editable installs (src/ensemble/config.py -> repo root).
_SOURCE_ROOT = Path(__file__).resolve().parents[2]


def load_config(env_file: str | Path | None = None) -> EnsembleConfig:
    if env_file is not None:
        load_env_file(env_file)
    else:
        # Current directory first, then the Ensemble checkout; neither overrides
        # variables that are already set in the environment.
        load_env_file(Path.cwd() / ".env")
        load_env_file(_SOURCE_ROOT / ".env")

    return EnsembleConfig(
        workspace=default_workspace(),
        max_file_bytes=int(os.getenv("ENSEMBLE_MAX_FILE_BYTES", "200000")),
        checkpoint_dir=Path(
            os.getenv("ENSEMBLE_CHECKPOINT_DIR", ".ensemble/checkpoints")
        ).expanduser(),
        context_token_budget=int(os.getenv("ENSEMBLE_CONTEXT_TOKEN_BUDGET", "12000")),
    )


def load_env_file(path: str | Path) -> bool:
    """Load simple KEY=VALUE lines without overriding variables already set.

    Replaces the python-dotenv dependency for the handful of ENSEMBLE_* settings.
    """
    env_path = Path(path).expanduser()
    if not env_path.is_file():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return True
