from __future__ import annotations

import requests
from langchain_openai import ChatOpenAI

from local_first.config import LocalFirstConfig


def build_chat_model(config: LocalFirstConfig) -> ChatOpenAI:
    return ChatOpenAI(
        model=config.llm_model,
        base_url=config.llm_base_url,
        api_key=config.api_key,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def models_url(config: LocalFirstConfig) -> str:
    return f"{config.llm_base_url.rstrip('/')}/models"


def fetch_models(config: LocalFirstConfig, timeout: float = 5.0) -> dict:
    response = requests.get(
        models_url(config),
        headers={"Authorization": f"Bearer {config.api_key}"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def health_check(config: LocalFirstConfig, timeout: float = 5.0) -> tuple[bool, str]:
    try:
        payload = fetch_models(config, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - CLI should return a concise status.
        return False, str(exc)
    count = len(payload.get("data", [])) if isinstance(payload, dict) else 0
    return True, f"{models_url(config)} responded with {count} model(s)"
