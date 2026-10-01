"""Minimal OpenAI-compatible chat client with streaming and tool calls.

Talks to llama.cpp (or the Ensemble router) over plain HTTP. No SDK required.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

import requests

from ensemble.config import EnsembleConfig

TextCallback = Callable[[str], None]


class LLMError(RuntimeError):
    """Raised when the model endpoint fails or returns an unusable response."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text, exactly as the model produced it


@dataclass
class AssistantTurn:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str | None = None

    def to_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                }
                for call in self.tool_calls
            ]
        return message


_TEXT_TOOL_CALL = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


def parse_stream(lines: Iterable[str], on_text: TextCallback | None = None) -> AssistantTurn:
    """Assemble an AssistantTurn from OpenAI-style SSE lines."""
    turn = AssistantTurn()
    parts: list[str] = []
    pending: dict[int, dict[str, str]] = {}
    last_index = 0

    for line in lines:
        if not line or not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if "error" in chunk:
            raise LLMError(f"Model endpoint error: {chunk['error']}")
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            text = delta.get("content")
            if text:
                parts.append(text)
                if on_text is not None:
                    on_text(text)
            for call in delta.get("tool_calls") or []:
                last_index = _slot_index(call, pending, last_index)
                slot = pending.setdefault(last_index, {"id": "", "name": "", "arguments": ""})
                function = call.get("function") or {}
                slot["id"] = call.get("id") or slot["id"]
                slot["name"] += function.get("name") or ""
                slot["arguments"] += function.get("arguments") or ""
            if choice.get("finish_reason"):
                turn.finish_reason = choice["finish_reason"]

    turn.content = "".join(parts)
    for index in sorted(pending):
        slot = pending[index]
        if slot["name"]:
            turn.tool_calls.append(
                ToolCall(slot["id"] or f"call_{index}", slot["name"], slot["arguments"] or "{}")
            )
    if not turn.tool_calls:
        _recover_text_tool_calls(turn)
    return turn


def _slot_index(call: dict[str, Any], pending: dict[int, dict[str, str]], last: int) -> int:
    """Pick the accumulator for a streamed tool-call fragment.

    Servers normally send `index`. Some omit it: then a fragment carrying a new
    `id` starts another call, and one without an id continues the previous call.
    """
    index = call.get("index")
    if isinstance(index, int):
        return index
    new_id = call.get("id")
    if pending and new_id and pending[last]["id"] and pending[last]["id"] != new_id:
        return max(pending) + 1
    return last


def parse_completion(body: dict[str, Any]) -> AssistantTurn:
    """Build an AssistantTurn from a non-streaming chat completion body."""
    if "error" in body:
        raise LLMError(f"Model endpoint error: {body['error']}")
    choices = body.get("choices") or []
    if not choices:
        raise LLMError("Model endpoint returned no choices")
    choice = choices[0]
    message = choice.get("message") or {}
    turn = AssistantTurn(content=message.get("content") or "", finish_reason=choice.get("finish_reason"))
    for index, call in enumerate(message.get("tool_calls") or []):
        function = call.get("function") or {}
        if function.get("name"):
            arguments = function.get("arguments") or "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            turn.tool_calls.append(
                ToolCall(call.get("id") or f"call_{index}", function["name"], arguments)
            )
    if not turn.tool_calls:
        _recover_text_tool_calls(turn)
    return turn


def _recover_text_tool_calls(turn: AssistantTurn) -> None:
    """Parse `<tool_call>{...}</tool_call>` blocks that small models emit as text."""
    matches = list(_TEXT_TOOL_CALL.finditer(turn.content))
    for index, match in enumerate(matches):
        try:
            data = json.loads(match.group(1))
            name = data["name"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        arguments = data.get("arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        turn.tool_calls.append(ToolCall(f"text_call_{index}", str(name), arguments))
    if turn.tool_calls:
        turn.content = _TEXT_TOOL_CALL.sub("", turn.content).strip()


class ChatClient:
    def __init__(
        self,
        config: EnsembleConfig,
        *,
        post: Callable[..., Any] = requests.post,
        timeout: tuple[float, float] = (10.0, 600.0),
    ) -> None:
        self._config = config
        self._post = post
        self._timeout = timeout

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        on_text: TextCallback | None = None,
    ) -> AssistantTurn:
        body: dict[str, Any] = {
            "model": self._config.llm_model,
            "messages": messages,
            "stream": True,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        if tools:
            body["tools"] = tools
        url = f"{self._config.llm_base_url.rstrip('/')}/chat/completions"
        try:
            response = self._post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                stream=True,
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise LLMError(f"Cannot reach {url}: {exc}") from exc
        try:
            if response.status_code >= 400:
                raise LLMError(f"{url} returned {response.status_code}: {response.text[:500]}")
            headers = getattr(response, "headers", None) or {}
            content_type = next((str(v) for k, v in headers.items() if k.lower() == "content-type"), "")
            if "application/json" in content_type.lower():
                # The server ignored stream=true and sent one JSON document.
                try:
                    turn = parse_completion(response.json())
                except ValueError as exc:
                    raise LLMError(f"{url} returned invalid JSON: {exc}") from exc
                if on_text is not None and turn.content:
                    on_text(turn.content)
                return turn
            return parse_stream(response.iter_lines(decode_unicode=True), on_text)
        except requests.RequestException as exc:
            raise LLMError(f"Stream from {url} failed: {exc}") from exc
        finally:
            response.close()
