"""Append-only JSONL session history."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class Session:
    def __init__(self, path: Path) -> None:
        self.path = path

    @classmethod
    def new(cls, directory: Path) -> Session:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return cls(directory / f"{stamp}.jsonl")

    @classmethod
    def latest(cls, directory: Path) -> Session | None:
        files = sorted(directory.glob("*.jsonl")) if directory.is_dir() else []
        return cls(files[-1]) if files else None

    def load(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        messages: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                messages.append(json.loads(line))
        return messages

    def append(self, message: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
