from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ensemble.safety import WorkspaceGuard


@dataclass(frozen=True)
class MemoryStore:
    path: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", self.path.expanduser())
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_note(self, title: str, body: str) -> None:
        timestamp = datetime.now(UTC).isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {title}\n\n")
            handle.write(f"- recorded_at: `{timestamp}`\n\n")
            handle.write(body.rstrip())
            handle.write("\n")

    def read(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")


def project_memory_for_workspace(guard: WorkspaceGuard) -> MemoryStore:
    return MemoryStore(guard.root / ".ensemble" / "memory.md")
