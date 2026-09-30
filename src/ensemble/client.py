from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ensemble.config import EnsembleConfig


@dataclass(frozen=True)
class EnsembleClient:
    config: EnsembleConfig

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    def models(self) -> dict[str, Any]:
        response = requests.get(
            f"{self.config.base_url}/models",
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def health(self) -> tuple[bool, str]:
        try:
            models = self.models()
        except requests.RequestException as exc:
            return False, str(exc)
        count = len(models.get("data", [])) if isinstance(models, dict) else 0
        return True, f"endpoint reachable; {count} model(s) advertised"

    def ask(self, prompt: str, *, context: str | None = None) -> str:
        user_content = prompt if context is None else f"{prompt}\n\nContext:\n{context}"
        response = requests.post(
            f"{self.config.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.config.model,
                "messages": [{"role": "user", "content": user_content}],
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices", [])
        if not choices:
            raise RuntimeError("endpoint returned no choices")
        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str):
            raise RuntimeError("endpoint returned no message content")
        return content
