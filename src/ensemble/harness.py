"""The Ensemble coding harness: a small tool-calling loop (a Python take on Pi)."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ensemble.config import EnsembleConfig
from ensemble.llm import ChatClient, LLMError, TextCallback
from ensemble.quality import inspect_response
from ensemble.safety import SafetyError, WorkspaceGuard
from ensemble.session import Session
from ensemble.skills import default_skill_root, inject_skill_cards
from ensemble.tools.coding import Tool, ToolError, coding_tools

EventCallback = Callable[[str, dict[str, Any]], None]

CONTEXT_FILES = ("AGENTS.md", "CLAUDE.md")
MAX_CONTEXT_CHARS = 8000
# ~12k tokens of history sent per request; local models have small windows.
DEFAULT_HISTORY_CHARS = 48000
_ELIDED = "[output elided to fit the context window]"

SYSTEM_PROMPT = """You are Ensemble, a small coding agent working in the user's workspace.
Use the available tools to read and change code. Work in small steps and verify.
Read a file before editing it. Prefer edit over rewriting; edits need exact text.
Be concise. Show file paths. Do not invent tool results."""


def build_system_prompt(guard: WorkspaceGuard, tools: list[Tool]) -> str:
    parts = [SYSTEM_PROMPT]
    names = ", ".join(tool.name for tool in tools)
    disabled = [
        label
        for label, enabled in (("writes", guard.allow_writes), ("shell", guard.allow_shell))
        if not enabled
    ]
    parts.append(f"Tools available: {names}.")
    if disabled:
        parts.append(
            f"Disabled by the operator: {', '.join(disabled)}. Propose patches as text instead."
        )
    for name in CONTEXT_FILES:
        path = guard.root / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")[:MAX_CONTEXT_CHARS]
            parts.append(f"Project instructions ({name}):\n{text.strip()}")
            break
    return "\n\n".join(parts)


def _size(message: dict[str, Any]) -> int:
    return len(json.dumps(message, ensure_ascii=False))


def fit_history(messages: list[dict[str, Any]], max_chars: int) -> list[dict[str, Any]]:
    """Return a copy of messages that fits max_chars; the stored history is untouched.

    Oldest tool outputs are elided first. If that is not enough, whole leading
    turns are dropped at a user-message boundary so no tool call loses its reply.
    The most recent user prompt is always kept.
    """
    fitted = [dict(m) for m in messages]
    total = sum(_size(m) for m in fitted)
    last_user = max((i for i, m in enumerate(fitted) if m.get("role") == "user"), default=0)
    for message in fitted[:last_user]:
        if total <= max_chars:
            return fitted
        if message.get("role") == "tool" and message.get("content") != _ELIDED:
            before = _size(message)
            message["content"] = _ELIDED
            total -= before - _size(message)
    start = 0
    while total > max_chars and start < last_user:
        total -= _size(fitted[start])
        start += 1
        while start < last_user and fitted[start].get("role") != "user":
            total -= _size(fitted[start])
            start += 1
    return fitted[start:]


class Agent:
    def __init__(
        self,
        config: EnsembleConfig,
        *,
        client: ChatClient | None = None,
        session: Session | None = None,
        messages: list[dict[str, Any]] | None = None,
        max_turns: int = 25,
        max_history_chars: int = DEFAULT_HISTORY_CHARS,
        on_text: TextCallback | None = None,
        on_event: EventCallback | None = None,
        checkpoint_root: Path | None = None,
        skill_root: Path | None = None,
    ) -> None:
        self.guard = WorkspaceGuard(
            config.workspace,
            allow_writes=config.allow_writes,
            allow_shell=config.allow_shell,
        )
        root = checkpoint_root or self.guard.root / ".ensemble" / "checkpoints"
        self.tools = coding_tools(self.guard, root)
        self._by_name = {tool.name: tool for tool in self.tools}
        self._client = client or ChatClient(config)
        self._session = session
        self._max_turns = max_turns
        self._max_history_chars = max_history_chars
        self._on_text = on_text
        self._on_event = on_event
        # Ensemble's own skill cards, never the workspace's: an untrusted repo's
        # markdown must not be injected into the prompt as if it were ours.
        self._skill_root = skill_root if skill_root is not None else default_skill_root()
        self._sequence: list[str] = []
        self.messages: list[dict[str, Any]] = list(messages or [])
        self._system = {
            "role": "system",
            "content": build_system_prompt(self.guard, self.tools),
        }

    def _emit(self, kind: str, **payload: Any) -> None:
        if self._on_event is not None:
            self._on_event(kind, payload)

    def _add(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        if self._session is not None:
            self._session.append(message)

    def run(self, prompt: str) -> str:
        """Run one user prompt to completion and return the final reply text."""
        skills = inject_skill_cards(prompt, self._skill_root) if self._skill_root.is_dir() else ""
        self._add({"role": "user", "content": f"{skills}\n\n{prompt}".strip()})
        specs = [tool.spec() for tool in self.tools]
        self._sequence = []  # loop detection is per prompt, not per session
        for _ in range(self._max_turns):
            turn = self._client.complete([self._system, *fit_history(self.messages, self._max_history_chars)], specs, self._on_text)
            self._add(turn.to_message())
            if not turn.tool_calls:
                for finding in inspect_response(turn.content):
                    self._emit("warning", code=finding.code, message=finding.message)
                return turn.content
            for call in turn.tool_calls:
                result = self._execute(call.name, call.arguments)
                self._add({"role": "tool", "tool_call_id": call.id, "content": result})
                self._sequence.append(f"{call.name}:{call.arguments}")
            if any(f.code == "repeated_tool_loop" for f in inspect_response("x", self._sequence)):
                self._emit("warning", code="repeated_tool_loop", message="Stopped: repeating calls.")
                return "[Stopped: the model repeated the same tool calls.]"
        self._emit("warning", code="max_turns", message=f"Stopped after {self._max_turns} turns.")
        return f"[Stopped after {self._max_turns} turns without a final answer.]"

    def _execute(self, name: str, raw_arguments: str) -> str:
        tool = self._by_name.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'. Available: {', '.join(self._by_name)}"
        try:
            arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
            if not isinstance(arguments, dict):
                raise ToolError("arguments must be a JSON object")
        except (json.JSONDecodeError, ToolError) as exc:
            return f"Error: invalid arguments for {name}: {exc}"
        self._emit("tool_start", name=name, arguments=arguments)
        try:
            result = tool.run(arguments)
        except (SafetyError, ToolError, OSError, UnicodeError) as exc:
            result = f"Error: {exc}"
        self._emit("tool_end", name=name, result=result)
        return result


__all__ = ["Agent", "LLMError", "build_system_prompt"]
