from __future__ import annotations

import subprocess
from dataclasses import dataclass

from local_first.safety import WorkspaceGuard


@dataclass(frozen=True)
class SandboxResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def run_command(
    guard: WorkspaceGuard,
    command: list[str],
    *,
    timeout_seconds: int = 60,
) -> SandboxResult:
    guard.require_shell()
    completed = subprocess.run(
        command,
        cwd=guard.root,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return SandboxResult(
        command=tuple(command),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
