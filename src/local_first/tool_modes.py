from __future__ import annotations

from pathlib import Path

from local_first.checkpoints import has_checkpoint
from local_first.safety import SafetyError, WorkspaceGuard


def plan_write(guard: WorkspaceGuard, relative_path: str | Path) -> Path:
    target = guard.resolve_write_path(relative_path)
    if target.exists():
        raise SafetyError("Write refuses to overwrite existing files. Use Edit.")
    return target


def plan_edit(
    guard: WorkspaceGuard,
    relative_path: str | Path,
    checkpoint_root: str | Path = "state/checkpoints",
) -> Path:
    target = guard.resolve_write_path(relative_path)
    if not target.exists():
        raise SafetyError("Edit requires an existing file. Use Write for new files.")
    if not has_checkpoint(guard, relative_path, checkpoint_root):
        raise SafetyError("Edit requires a checkpoint before modification.")
    return target
