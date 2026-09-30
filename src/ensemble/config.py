from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ensemble.paths import default_workspace

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


@dataclass(frozen=True)
class EnsembleConfig:
    base_url: str
    model: str
    api_key: str
    workspace: Path
    max_file_bytes: int
    checkpoint_dir: Path
    context_token_budget: int


def load_config(env_file: str | Path | None = None) -> EnsembleConfig:
    load_dotenv(env_file) if env_file is not None else load_dotenv()

    return EnsembleConfig(
        base_url=os.getenv("ENSEMBLE_BASE_URL", "http://127.0.0.1:8090/v1").rstrip("/"),
        model=os.getenv("ENSEMBLE_MODEL", "auto"),
        api_key=os.getenv("ENSEMBLE_API_KEY", "ensemble"),
        workspace=default_workspace(),
        max_file_bytes=int(os.getenv("ENSEMBLE_MAX_FILE_BYTES", "200000")),
        checkpoint_dir=Path(
            os.getenv("ENSEMBLE_CHECKPOINT_DIR", ".ensemble/checkpoints")
        ).expanduser(),
        context_token_budget=int(os.getenv("ENSEMBLE_CONTEXT_TOKEN_BUDGET", "12000")),
    )
