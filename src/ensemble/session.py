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
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # torn write from a crash; the rest of the history is still good
        return _drop_dangling_tool_calls(messages)

    def append(self, message: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("ab+") as handle:
            # Start on a fresh line if a crash left a torn, unterminated record.
            if handle.tell() and (handle.seek(-1, 2), handle.read(1))[1] != b"\n":
                handle.write(b"\n")
            handle.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))


def _drop_dangling_tool_calls(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove assistant tool calls with missing results, and orphaned results.

    Chat endpoints reject a history where a tool call has no matching reply, which
    is what an interrupted run leaves behind.
    """
    answered = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    kept: list[dict[str, Any]] = []
    kept_ids: set[str] = set()
    for message in messages:
        calls = message.get("tool_calls") if message.get("role") == "assistant" else None
        if calls:
            ids = {call.get("id") for call in calls}
            if not ids <= answered:
                continue
            kept_ids |= ids
        elif message.get("role") == "tool" and message.get("tool_call_id") not in kept_ids:
            continue
        kept.append(message)
    return kept
