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
    profile: str
    max_tokens: int
    temperature: float
    workspace: Path
    allow_writes: bool
    allow_shell: bool
    max_file_bytes: int


def load_config(
    env_file: str | Path | None = None,
    *,
    profile_override: str | None = None,
) -> LocalFirstConfig:
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    workspace = Path(
        os.getenv("LOCAL_FIRST_WORKSPACE", "/home/jarvis/jarvis/talent-beacon")
    ).expanduser()

    profile_name = profile_override if profile_override is not None else os.getenv("LOCAL_FIRST_PROFILE", "")
    profile_base_url = None
    profile_model = None
    profile_api_key = None
    profile_max_tokens = None
    profile_temperature = None
    if profile_name:
        from local_first.profiles import load_named_profile

        profile = load_named_profile(profile_name)
        profile_base_url = profile.base_url
        profile_model = profile.model
        profile_api_key = profile.api_key
        profile_max_tokens = profile.max_tokens
        profile_temperature = profile.temperature

    return LocalFirstConfig(
        llm_base_url=os.getenv(
            "LOCAL_FIRST_LLM_BASE_URL",
            profile_base_url or "http://localhost:8080/v1",
        ),
        llm_model=os.getenv(
            "LOCAL_FIRST_LLM_MODEL",
            profile_model or "qwen3.6-35b-a3b-ud-q4_k_xl",
        ),
        api_key=os.getenv("LOCAL_FIRST_API_KEY", profile_api_key or "local-first"),
        profile=profile_name,
        max_tokens=int(os.getenv("LOCAL_FIRST_MAX_TOKENS", profile_max_tokens or "1024")),
        temperature=float(
            os.getenv("LOCAL_FIRST_TEMPERATURE", profile_temperature or "0.2")
        ),
        workspace=workspace,
        allow_writes=_bool_env("LOCAL_FIRST_ALLOW_WRITES", False),
        allow_shell=_bool_env("LOCAL_FIRST_ALLOW_SHELL", False),
        max_file_bytes=int(os.getenv("LOCAL_FIRST_MAX_FILE_BYTES", "200000")),
    )
