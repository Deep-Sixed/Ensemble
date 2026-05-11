from __future__ import annotations

from local_first.safety import WorkspaceGuard


def shell_disabled_message(guard: WorkspaceGuard) -> str:
    guard.require_shell()
    return "Shell execution is enabled, but v1 does not implement command execution yet."
