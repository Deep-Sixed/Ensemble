from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SafetyError(ValueError):
    """Raised when a requested operation crosses a Local-First boundary."""


@dataclass(frozen=True)
class WorkspaceGuard:
    root: Path
    allow_writes: bool = False
    allow_shell: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.expanduser().resolve())

    def resolve_read_path(self, path: str | Path) -> Path:
        candidate = self._resolve(path)
        if not candidate.exists():
            raise SafetyError(f"Path does not exist: {candidate}")
        return candidate

    def resolve_write_path(self, path: str | Path) -> Path:
        if not self.allow_writes:
            raise SafetyError("Writes are disabled. Set LOCAL_FIRST_ALLOW_WRITES=true.")
        return self._resolve(path)

    def require_shell(self) -> None:
        if not self.allow_shell:
            raise SafetyError("Shell execution is disabled. Set LOCAL_FIRST_ALLOW_SHELL=true.")

    def _resolve(self, path: str | Path) -> Path:
        raw = Path(path).expanduser()
        candidate = raw if raw.is_absolute() else self.root / raw
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SafetyError(f"Path escapes workspace: {resolved}") from exc
        return resolved
