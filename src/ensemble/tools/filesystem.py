from __future__ import annotations

from pathlib import Path

from ensemble.safety import SafetyError, WorkspaceGuard


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
    for path in sorted(root.rglob("*")):
        if len(files) >= limit:
            break
        if _skip_path(path):
            continue
        files.append(str(path.relative_to(guard.root)))
    return files


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


def _skip_path(path: Path) -> bool:
    skip_names = {
        ".git",
        ".venv",
        "__pycache__",
        "node_modules",
        ".next",
        "dist",
        "build",
    }
    return any(part in skip_names for part in path.parts)
