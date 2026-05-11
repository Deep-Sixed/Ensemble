from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModelProfile:
    name: str
    provider: str
    model: str
    base_url: str
    api_key_env: str
    context_window: int
    max_tokens: int
    temperature: float
    reasoning: bool
    cost: dict[str, float]

    @property
    def api_key(self) -> str:
        return os.getenv(self.api_key_env, "local-first")


def profile_dir(root: str | Path = ".") -> Path:
    return Path(root) / "profiles"


def list_profiles(root: str | Path = ".") -> list[Path]:
    return sorted(profile_dir(root).glob("*.json"))


def load_profile(path: str | Path) -> ModelProfile:
    profile_path = Path(path)
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    return _profile_from_payload(profile_path.stem, payload)


def load_named_profile(name: str, root: str | Path = ".") -> ModelProfile:
    candidates = [
        profile_dir(root) / name,
        profile_dir(root) / f"{name}.json",
        Path(name),
    ]
    for candidate in candidates:
        if candidate.exists():
            return load_profile(candidate)
    raise FileNotFoundError(f"Profile not found: {name}")


def _profile_from_payload(name: str, payload: dict[str, Any]) -> ModelProfile:
    return ModelProfile(
        name=name,
        provider=str(payload["provider"]),
        model=str(payload["model"]),
        base_url=str(payload["base_url"]),
        api_key_env=str(payload.get("api_key_env", "LOCAL_FIRST_API_KEY")),
        context_window=int(payload.get("context_window", 4096)),
        max_tokens=int(payload.get("max_tokens", 512)),
        temperature=float(payload.get("temperature", 0.2)),
        reasoning=bool(payload.get("reasoning", False)),
        cost={str(k): float(v) for k, v in payload.get("cost", {}).items()},
    )
