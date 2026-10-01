"""The four coding tools: read, write, edit, bash.

Every tool runs through WorkspaceGuard. Only tools the operator has enabled are
advertised to the model, which keeps the prompt small for local models.
"""
from __future__ import annotations

import difflib
import os
import signal
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ensemble.checkpoints import create_checkpoint
from ensemble.safety import SafetyError, WorkspaceGuard
from ensemble.tools.filesystem import list_files
from ensemble.tool_modes import plan_write

MAX_OUTPUT_LINES = 2000
MAX_OUTPUT_BYTES = 50 * 1024
DEFAULT_BASH_TIMEOUT = 120.0


class ToolError(ValueError):
    """Raised for bad tool arguments; reported back to the model as text."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[[dict[str, Any]], str]

    def spec(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required}


def _str_arg(args: dict[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str):
        raise ToolError(f"'{key}' must be a string")
    return value


def _int_arg(args: dict[str, Any], key: str) -> int | None:
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ToolError(f"'{key}' must be an integer")
    return value


def truncate_head(text: str) -> tuple[str, bool]:
    """Keep the first lines/bytes of text (used for file reads)."""
    lines = text.splitlines(keepends=True)
    clipped = len(lines) > MAX_OUTPUT_LINES
    out = "".join(lines[:MAX_OUTPUT_LINES])
    raw = out.encode("utf-8")
    if len(raw) > MAX_OUTPUT_BYTES:
        out = raw[:MAX_OUTPUT_BYTES].decode("utf-8", errors="ignore")
        clipped = True
    return out, clipped


def truncate_tail(text: str) -> tuple[str, bool]:
    """Keep the last lines/bytes of text (used for command output)."""
    lines = text.splitlines(keepends=True)
    clipped = len(lines) > MAX_OUTPUT_LINES
    out = "".join(lines[-MAX_OUTPUT_LINES:])
    raw = out.encode("utf-8")
    if len(raw) > MAX_OUTPUT_BYTES:
        out = raw[-MAX_OUTPUT_BYTES:].decode("utf-8", errors="ignore")
        clipped = True
    return out, clipped


def read_tool(guard: WorkspaceGuard) -> Tool:
    def run(args: dict[str, Any]) -> str:
        path = guard.resolve_read_path(_str_arg(args, "path"))
        if path.is_dir():
            return "\n".join(list_files(guard, str(path.relative_to(guard.root)))) or "(empty)"
        offset = _int_arg(args, "offset") or 1
        limit = _int_arg(args, "limit")
        if offset < 1 or (limit is not None and limit < 1):
            raise ToolError("'offset' and 'limit' must be positive")
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        total = len(lines)
        if offset > max(total, 1):
            raise ToolError(f"offset {offset} is beyond end of file ({total} lines)")
        end = total if limit is None else min(total, offset - 1 + limit)
        text, clipped = truncate_head("".join(lines[offset - 1 : end]))
        shown = len(text.splitlines())
        if clipped:
            next_offset = offset + shown
            text += f"\n[Truncated at {shown} lines. Use offset={next_offset} to continue.]"
        elif end < total:
            text += f"\n[{total - end} more lines. Use offset={end + 1} to continue.]"
        return text or "(empty file)"

    return Tool(
        "read",
        "Read a file (or list a directory). Output is truncated; use offset/limit for large files.",
        _schema(
            {
                "path": {"type": "string", "description": "Path relative to the workspace"},
                "offset": {"type": "integer", "description": "First line to read (1-indexed)"},
                "limit": {"type": "integer", "description": "Maximum number of lines"},
            },
            ["path"],
        ),
        run,
    )


def write_tool(guard: WorkspaceGuard) -> Tool:
    def run(args: dict[str, Any]) -> str:
        target = plan_write(guard, _str_arg(args, "path"))
        content = _str_arg(args, "content")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Created {target.relative_to(guard.root)} ({len(content)} chars)"

    return Tool(
        "write",
        "Create a NEW file. Refuses to overwrite; use edit for existing files.",
        _schema(
            {
                "path": {"type": "string", "description": "Path relative to the workspace"},
                "content": {"type": "string", "description": "Full file content"},
            },
            ["path", "content"],
        ),
        run,
    )


def edit_tool(guard: WorkspaceGuard, checkpoint_root: Path) -> Tool:
    def run(args: dict[str, Any]) -> str:
        relative = _str_arg(args, "path")
        old = _str_arg(args, "old_text")
        new = _str_arg(args, "new_text")
        if not old:
            raise ToolError("'old_text' must not be empty")
        target = guard.resolve_write_path(relative)
        if not target.exists():
            raise SafetyError("Edit requires an existing file. Use write for new files.")
        # Bytes, not read_text/write_text: those translate CRLF to LF and would
        # rewrite every line ending in the file.
        original = target.read_bytes().decode("utf-8")
        if "\r\n" in original:
            old = old.replace("\r\n", "\n").replace("\n", "\r\n")
            new = new.replace("\r\n", "\n").replace("\n", "\r\n")
        count = original.count(old)
        if count == 0:
            raise ToolError("old_text not found. It must match the file exactly, incl. whitespace.")
        if count > 1:
            raise ToolError(f"old_text matches {count} places. Include more surrounding lines.")
        checkpoint = create_checkpoint(guard, relative, checkpoint_root)
        if not checkpoint.snapshot.is_file():
            raise SafetyError("Edit requires a checkpoint before modification.")
        updated = original.replace(old, new, 1)
        target.write_bytes(updated.encode("utf-8"))
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{relative}",
                tofile=f"b/{relative}",
                n=2,
            )
        )
        shown, _ = truncate_head(diff)
        return f"Edited {relative} (checkpointed)\n{shown}"

    return Tool(
        "edit",
        "Replace one exact, unique occurrence of old_text with new_text in an existing file.",
        _schema(
            {
                "path": {"type": "string", "description": "Path relative to the workspace"},
                "old_text": {"type": "string", "description": "Exact text to replace (unique)"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            ["path", "old_text", "new_text"],
        ),
        run,
    )


# Variables the model's shell may inherit. Everything else (API keys, tokens
# loaded into the operator's shell) is withheld.
_SHELL_ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "TMPDIR", "TZ")
_TAIL_CAP_BYTES = 4 * MAX_OUTPUT_BYTES


def _shell_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in _SHELL_ENV_ALLOW}


class _TailReader(threading.Thread):
    """Drain a pipe, keeping only the last _TAIL_CAP_BYTES so output stays bounded."""

    def __init__(self, stream: Any) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._buffer = bytearray()
        self.dropped = False

    def run(self) -> None:
        while chunk := self._stream.read1(65536):
            self._buffer += chunk
            if len(self._buffer) > _TAIL_CAP_BYTES:
                del self._buffer[: len(self._buffer) - _TAIL_CAP_BYTES]
                self.dropped = True

    def result(self) -> bytes:
        # A backgrounded grandchild can hold the pipe open; don't wait on it forever.
        self.join(timeout=2.0)
        return bytes(self._buffer)


def bash_tool(guard: WorkspaceGuard) -> Tool:
    def run(args: dict[str, Any]) -> str:
        guard.require_shell()
        command = _str_arg(args, "command")
        timeout = args.get("timeout", DEFAULT_BASH_TIMEOUT)
        if isinstance(timeout, bool) or not isinstance(timeout, int | float) or timeout <= 0:
            raise ToolError("'timeout' must be a positive number of seconds")
        process = subprocess.Popen(
            ["bash", "-c", command],
            cwd=guard.root,
            env=_shell_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        tail = _TailReader(process.stdout)
        tail.start()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        finally:
            if process.poll() is None:  # e.g. KeyboardInterrupt
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        text, clipped = truncate_tail(tail.result().decode("utf-8", errors="replace"))
        clipped = clipped or tail.dropped
        if clipped:
            text = "[Output truncated to the last part]\n" + text
        if timed_out:
            text += f"\n[Timed out after {timeout:g}s and was killed]"
        elif process.returncode != 0:
            text += f"\n[exit code {process.returncode}]"
        return text or "(no output)"

    return Tool(
        "bash",
        "Run a shell command in the workspace. Stdin is closed; output is tail-truncated.",
        _schema(
            {
                "command": {"type": "string", "description": "Command to run with bash -c"},
                "timeout": {"type": "number", "description": "Seconds before the command is killed"},
            },
            ["command"],
        ),
        run,
    )


def coding_tools(guard: WorkspaceGuard, checkpoint_root: Path) -> list[Tool]:
    """Return only the tools the operator has enabled (read is always on)."""
    tools = [read_tool(guard)]
    if guard.allow_writes:
        tools += [write_tool(guard), edit_tool(guard, checkpoint_root)]
    if guard.allow_shell:
        tools.append(bash_tool(guard))
    return tools
