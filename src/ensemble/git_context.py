from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitContext:
    branch: str | None
    status: list[str]
    staged_diff: str
    unstaged_diff: str

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def changed_paths(self) -> set[str]:
        """Workspace-relative paths from `git status --short` (rename targets included)."""
        paths: set[str] = set()
        for line in self.status:
            entry = line[3:].strip()
            if " -> " in entry:
                entry = entry.split(" -> ", 1)[1]
            if entry:
                paths.add(entry.strip('"'))
        return paths

    def render(self) -> str:
        parts: list[str] = []
        if self.branch:
            parts.append(f"branch: {self.branch}")
        if self.status:
            parts.append("status:\n" + "\n".join(self.status))
        if self.staged_diff:
            parts.append("staged diff:\n" + self.staged_diff)
        if self.unstaged_diff:
            parts.append("unstaged diff:\n" + self.unstaged_diff)
        return "\n\n".join(parts)


def collect_git_context(root: str | Path, *, max_chars: int = 20_000) -> GitContext:
    cwd = Path(root).resolve()
    if not (cwd / ".git").exists():
        return GitContext(None, [], "", "")

    branch = _git(cwd, "branch", "--show-current").strip() or None
    status = [line for line in _git(cwd, "status", "--short").splitlines() if line.strip()]
    staged = _git(cwd, "diff", "--cached", "--no-ext-diff", "--unified=3")
    unstaged = _git(cwd, "diff", "--no-ext-diff", "--unified=3")

    return GitContext(
        branch=branch,
        status=status,
        staged_diff=_clip(staged, max_chars),
        unstaged_diff=_clip(unstaged, max_chars),
    )


def _git(cwd: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def _clip(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
