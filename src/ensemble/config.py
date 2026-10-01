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


def _env(name: str) -> str | None:
    return os.getenv(name)


def _bool_env(name: str, default: bool = False) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EnsembleConfig:
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
) -> EnsembleConfig:
    if env_file is not None:
        load_dotenv(env_file)
    else:
        load_dotenv()

    workspace = default_workspace()

    if profile_override is not None:
        profile_name = profile_override
    else:
        profile_name = (_env("ENSEMBLE_PROFILE") or "").strip()

    profile_base_url = None
    profile_model = None
    profile_api_key = None
    profile_max_tokens = None
    profile_temperature = None
    if profile_name:
        from ensemble.profiles import load_named_profile

        profile = load_named_profile(profile_name)
        profile_base_url = profile.base_url
        profile_model = profile.model
        profile_api_key = profile.api_key
        profile_max_tokens = profile.max_tokens
        profile_temperature = profile.temperature

    # `is None`, not `or`: a profile temperature of 0 is valid and falsy.
    default_max_tokens = 1024 if profile_max_tokens is None else int(profile_max_tokens)
    default_temperature = 0.2 if profile_temperature is None else float(profile_temperature)

    # CLI `--profile` on commands like `health` and `models`: use the profile JSON
    # for LLM endpoint fields so ENSEMBLE_LLM_BASE_URL does not mask base_url.
    if profile_override is not None:
        return EnsembleConfig(
            llm_base_url=profile_base_url or "http://localhost:8888/v1",
            llm_model=profile_model or "qwen2.5-coder-7b-instruct-q4_k_m",
            api_key=profile_api_key or "ensemble",
            profile=profile_name,
            max_tokens=default_max_tokens,
            temperature=default_temperature,
            workspace=workspace,
            allow_writes=_bool_env("ENSEMBLE_ALLOW_WRITES", False),
            allow_shell=_bool_env("ENSEMBLE_ALLOW_SHELL", False),
            max_file_bytes=int(_env("ENSEMBLE_MAX_FILE_BYTES") or "200000"),
        )

    return EnsembleConfig(
        llm_base_url=(
            _env("ENSEMBLE_LLM_BASE_URL")
            or profile_base_url
            or "http://localhost:8888/v1"
        ),
        llm_model=(
            _env("ENSEMBLE_LLM_MODEL")
            or profile_model
            or "qwen2.5-coder-7b-instruct-q4_k_m"
        ),
        api_key=_env("ENSEMBLE_API_KEY") or profile_api_key or "ensemble",
        profile=profile_name,
        max_tokens=int(_env("ENSEMBLE_MAX_TOKENS") or default_max_tokens),
        temperature=float(_env("ENSEMBLE_TEMPERATURE") or default_temperature),
        workspace=workspace,
        allow_writes=_bool_env("ENSEMBLE_ALLOW_WRITES", False),
        allow_shell=_bool_env("ENSEMBLE_ALLOW_SHELL", False),
        max_file_bytes=int(_env("ENSEMBLE_MAX_FILE_BYTES") or "200000"),
    )
