from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ensemble.safety import WorkspaceGuard


DEFAULT_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    ".ensemble",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
}


@dataclass(frozen=True)
class WorkspaceFile:
    path: Path
    relative_path: str
    size_bytes: int


def discover_workspace_files(
    guard: WorkspaceGuard,
    *,
    max_file_bytes: int = 200_000,
    excludes: set[str] | None = None,
) -> list[WorkspaceFile]:
    excluded = excludes or DEFAULT_EXCLUDES
    files: list[WorkspaceFile] = []

    for path in sorted(guard.root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(guard.root)
        if any(part in excluded for part in relative.parts):
            continue
        try:
            resolved = guard.resolve_read_path(relative)
            size = resolved.stat().st_size
        except (OSError, ValueError):
            continue
        if size > max_file_bytes:
            continue
        if _looks_binary(resolved):
            continue
        files.append(
            WorkspaceFile(
                path=resolved,
                relative_path=relative.as_posix(),
                size_bytes=size,
            )
        )
    return files


def _looks_binary(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\x00" in sample
