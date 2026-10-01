from __future__ import annotations

import os
from pathlib import Path

from ensemble.safety import SafetyError, WorkspaceGuard


_SKIP_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    ".next",
    "dist",
    "build",
}


def list_files(
    guard: WorkspaceGuard,
    relative_path: str = ".",
    *,
    limit: int = 200,
) -> list[str]:
    root = guard.resolve_read_path(relative_path)
    if not root.is_dir():
        raise SafetyError(f"Not a directory: {root}")

    files: list[str] = []
    _walk(root, guard.root, files, limit)
    return files


def _walk(directory: Path, workspace: Path, files: list[str], limit: int) -> None:
    """Sorted depth-first listing that never descends into skipped directories."""
    try:
        entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
    except OSError:
        return
    for entry in entries:
        if len(files) >= limit:
            return
        if entry.name in _SKIP_NAMES:
            continue
        files.append(str(Path(entry.path).relative_to(workspace)))
        if entry.is_dir(follow_symlinks=False):
            _walk(Path(entry.path), workspace, files, limit)


def read_file(
    guard: WorkspaceGuard,
    relative_path: str,
    *,
    max_bytes: int,
) -> str:
    path = guard.resolve_read_path(relative_path)
    if not path.is_file():
        raise SafetyError(f"Not a file: {path}")

    size = path.stat().st_size
    if size > max_bytes:
        raise SafetyError(f"File is {size} bytes; max is {max_bytes} bytes")

    return path.read_text(encoding="utf-8", errors="replace")
