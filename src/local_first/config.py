from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LocalFirstConfig:
    llm_base_url: str
    llm_model: str
    api_key: str
    workspace: Path
    allow_writes: bool
    allow_shell: bool
    max_file_bytes: int


def load_config(env_file: str | Path | None = None) -> LocalFirstConfig:
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    workspace = Path(
        os.getenv("LOCAL_FIRST_WORKSPACE", "/home/jarvis/jarvis/talent-beacon")
    ).expanduser()

    return LocalFirstConfig(
        llm_base_url=os.getenv("LOCAL_FIRST_LLM_BASE_URL", "http://localhost:8080/v1"),
        llm_model=os.getenv(
            "LOCAL_FIRST_LLM_MODEL", "qwen3.6-35b-a3b-ud-q4_k_xl"
        ),
        api_key=os.getenv("LOCAL_FIRST_API_KEY", "local-first"),
        workspace=workspace,
        allow_writes=_bool_env("LOCAL_FIRST_ALLOW_WRITES", False),
        allow_shell=_bool_env("LOCAL_FIRST_ALLOW_SHELL", False),
        max_file_bytes=int(os.getenv("LOCAL_FIRST_MAX_FILE_BYTES", "200000")),
    )
