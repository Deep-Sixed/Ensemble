from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ensemble.config import EnsembleConfig
from ensemble.harness import Agent
from ensemble.llm import AssistantTurn, ChatClient, LLMError, ToolCall, parse_stream
from ensemble.session import Session


def make_config(workspace: Path, *, writes: bool = False, shell: bool = False) -> EnsembleConfig:
    return EnsembleConfig(
        llm_base_url="http://llm.test/v1",
        llm_model="test-model",
        api_key="k",
        profile="",
        max_tokens=256,
        temperature=0.0,
        workspace=workspace,
        allow_writes=writes,
        allow_shell=shell,
        max_file_bytes=200000,
    )


def sse(*chunks: dict[str, Any]) -> list[str]:
    return [f"data: {json.dumps(chunk)}" for chunk in chunks] + ["data: [DONE]"]


class ScriptedClient:
    """Stands in for ChatClient: returns queued turns and records requests."""

    def __init__(self, *turns: AssistantTurn) -> None:
        self.turns = list(turns)
        self.requests: list[list[dict[str, Any]]] = []

    def complete(self, messages, tools=None, on_text=None) -> AssistantTurn:
        self.requests.append(messages)
        turn = self.turns.pop(0)
        if on_text and turn.content:
            on_text(turn.content)
        return turn


def call(name: str, **arguments: Any) -> ToolCall:
    return ToolCall(f"id_{name}", name, json.dumps(arguments))


def tool_turn(*calls: ToolCall) -> AssistantTurn:
    return AssistantTurn(tool_calls=list(calls), finish_reason="tool_calls")


def final(text: str) -> AssistantTurn:
    return AssistantTurn(content=text, finish_reason="stop")


# --- streaming parser -------------------------------------------------------


def test_parse_stream_assembles_text_and_fragmented_tool_calls() -> None:
    seen: list[str] = []
    turn = parse_stream(
        sse(
            {"choices": [{"delta": {"content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "id": "c1", "function": {"name": "re", "arguments": '{"pa'}}
            ]}}]},
            {"choices": [{"delta": {"tool_calls": [
                {"index": 0, "function": {"name": "ad", "arguments": 'th": "a.py"}'}}
            ]}, "finish_reason": "tool_calls"}]},
        ),
        seen.append,
    )
    assert turn.content == "Hello"
    assert seen == ["Hel", "lo"]
    assert turn.tool_calls == [ToolCall("c1", "read", '{"path": "a.py"}')]
    assert turn.finish_reason == "tool_calls"


def test_parse_stream_recovers_text_tool_calls() -> None:
    body = 'Sure.<tool_call>{"name": "read", "arguments": {"path": "x"}}</tool_call>'
    turn = parse_stream(sse({"choices": [{"delta": {"content": body}}]}))
    assert turn.content == "Sure."
    assert turn.tool_calls[0].name == "read"
    assert json.loads(turn.tool_calls[0].arguments) == {"path": "x"}


def test_parse_stream_raises_on_error_chunk() -> None:
    with pytest.raises(LLMError):
        parse_stream(sse({"error": {"message": "boom"}}))


class FakeResponse:
    def __init__(self, status: int, lines: list[str], text: str = "") -> None:
        self.status_code, self._lines, self.text = status, lines, text
        self.closed = False

    def iter_lines(self, decode_unicode: bool = False):
        return iter(self._lines)

    def close(self) -> None:
        self.closed = True


def test_chat_client_posts_openai_request(tmp_path: Path) -> None:
    captured: dict[str, Any] = {}
    response = FakeResponse(200, sse({"choices": [{"delta": {"content": "hi"}}]}))

    def post(url: str, **kwargs: Any) -> FakeResponse:
        captured.update(url=url, **kwargs)
        return response

    client = ChatClient(make_config(tmp_path), post=post)
    turn = client.complete([{"role": "user", "content": "yo"}], [{"type": "function"}])
    assert turn.content == "hi"
    assert captured["url"] == "http://llm.test/v1/chat/completions"
    assert captured["json"]["model"] == "test-model"
    assert captured["json"]["stream"] is True
    assert captured["json"]["tools"] == [{"type": "function"}]
    assert captured["headers"]["Authorization"] == "Bearer k"
    assert response.closed


def test_chat_client_reports_http_errors(tmp_path: Path) -> None:
    client = ChatClient(
        make_config(tmp_path), post=lambda url, **kw: FakeResponse(500, [], "server exploded")
    )
    with pytest.raises(LLMError, match="500"):
        client.complete([])


# --- agent loop and tools ---------------------------------------------------


def test_read_only_by_default_advertises_only_read(tmp_path: Path) -> None:
    agent = Agent(make_config(tmp_path), client=ScriptedClient())
    assert [tool.name for tool in agent.tools] == ["read"]
    full = Agent(make_config(tmp_path, writes=True, shell=True), client=ScriptedClient())
    assert [tool.name for tool in full.tools] == ["read", "write", "edit", "bash"]


def test_agent_reads_file_then_answers(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one\ntwo\nthree\n")
    client = ScriptedClient(tool_turn(call("read", path="a.py", offset=2)), final("done"))
    agent = Agent(make_config(tmp_path), client=client)
    assert agent.run("look at a.py") == "done"
    tool_message = agent.messages[2]
    assert tool_message["role"] == "tool"
    assert tool_message["content"].startswith("two")
    assert "one" not in tool_message["content"]
    # system prompt is sent but not stored in history
    assert client.requests[0][0]["role"] == "system"
    assert all(m["role"] != "system" for m in agent.messages)


def test_read_truncates_and_hints_continuation(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("\n".join(str(i) for i in range(5000)))
    agent = Agent(make_config(tmp_path), client=ScriptedClient())
    result = agent.tools[0].run({"path": "big.txt"})
    assert "offset=2001" in result


def test_workspace_escape_is_reported_not_raised(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (tmp_path / "secret.txt").write_text("nope")
    client = ScriptedClient(tool_turn(call("read", path="../secret.txt")), final("ok"))
    agent = Agent(make_config(workspace), client=client)
    agent.run("go")
    assert "escapes workspace" in agent.messages[2]["content"]


def test_write_creates_but_refuses_overwrite(tmp_path: Path) -> None:
    client = ScriptedClient(
        tool_turn(call("write", path="new/f.txt", content="hi")),
        tool_turn(call("write", path="new/f.txt", content="again")),
        final("done"),
    )
    agent = Agent(make_config(tmp_path, writes=True), client=client)
    agent.run("write it")
    assert (tmp_path / "new/f.txt").read_text() == "hi"
    assert agent.messages[2]["content"].startswith("Created")
    assert "refuses to overwrite" in agent.messages[4]["content"]


def test_edit_checkpoints_then_replaces_unique_text(tmp_path: Path) -> None:
    target = tmp_path / "f.py"
    target.write_text("a = 1\nb = 2\n")
    client = ScriptedClient(
        tool_turn(call("edit", path="f.py", old_text="a = 1", new_text="a = 10")),
        final("done"),
    )
    agent = Agent(make_config(tmp_path, writes=True), client=client)
    agent.run("edit")
    assert target.read_text() == "a = 10\nb = 2\n"
    snapshots = list((tmp_path / ".ensemble" / "checkpoints").glob("*__f.py"))
    assert len(snapshots) == 1
    assert snapshots[0].read_text() == "a = 1\nb = 2\n"
    assert "+a = 10" in agent.messages[2]["content"]


def test_edit_rejects_missing_and_ambiguous_matches(tmp_path: Path) -> None:
    (tmp_path / "f.py").write_text("x\nx\n")
    agent = Agent(make_config(tmp_path, writes=True), client=ScriptedClient())
    edit = next(tool for tool in agent.tools if tool.name == "edit")
    with pytest.raises(Exception, match="matches 2"):
        edit.run({"path": "f.py", "old_text": "x", "new_text": "y"})
    with pytest.raises(Exception, match="not found"):
        edit.run({"path": "f.py", "old_text": "zzz", "new_text": "y"})
    assert (tmp_path / "f.py").read_text() == "x\nx\n"


def test_bash_runs_in_workspace_and_reports_exit_code(tmp_path: Path) -> None:
    agent = Agent(make_config(tmp_path, shell=True), client=ScriptedClient())
    bash = next(tool for tool in agent.tools if tool.name == "bash")
    assert bash.run({"command": "pwd"}).strip() == str(tmp_path.resolve())
    assert "[exit code 3]" in bash.run({"command": "echo hi; exit 3"})


def test_bash_timeout_kills_process_group(tmp_path: Path) -> None:
    agent = Agent(make_config(tmp_path, shell=True), client=ScriptedClient())
    bash = next(tool for tool in agent.tools if tool.name == "bash")
    assert "Timed out" in bash.run({"command": "sleep 30", "timeout": 0.5})


def test_unknown_tool_and_bad_arguments_become_tool_errors(tmp_path: Path) -> None:
    client = ScriptedClient(
        tool_turn(
            call("bash", command="ls"),
            ToolCall("c2", "read", "{not json"),
            call("read", path=5),
        ),
        final("ok"),
    )
    agent = Agent(make_config(tmp_path), client=client)
    agent.run("go")
    results = [m["content"] for m in agent.messages if m["role"] == "tool"]
    assert "unknown tool 'bash'" in results[0]
    assert "invalid arguments" in results[1]
    assert "must be a string" in results[2]


def test_agent_stops_on_repeated_tool_loop(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x")
    turns = [tool_turn(call("read", path="a.txt")) for _ in range(10)]
    agent = Agent(make_config(tmp_path), client=ScriptedClient(*turns))
    assert "repeated" in agent.run("loop")


def test_agent_stops_at_max_turns(tmp_path: Path) -> None:
    turns = [tool_turn(call("read", path=f"{i}.txt")) for i in range(5)]
    agent = Agent(make_config(tmp_path), client=ScriptedClient(*turns), max_turns=2)
    assert "2 turns" in agent.run("loop")


def test_agents_md_is_loaded_into_system_prompt(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Always use tabs.")
    client = ScriptedClient(final("ok"))
    Agent(make_config(tmp_path), client=client).run("hi")
    assert "Always use tabs." in client.requests[0][0]["content"]


def test_session_persists_and_resumes(tmp_path: Path) -> None:
    directory = tmp_path / "sessions"
    first = Agent(
        make_config(tmp_path),
        client=ScriptedClient(final("hello")),
        session=Session.new(directory),
    )
    first.run("hi")
    latest = Session.latest(directory)
    assert latest is not None
    resumed = Agent(
        make_config(tmp_path),
        client=ScriptedClient(final("again")),
        session=latest,
        messages=latest.load(),
    )
    resumed.run("more")
    assert [m["role"] for m in resumed.messages] == ["user", "assistant", "user", "assistant"]
    assert len(latest.load()) == 4


@pytest.mark.parametrize(
    "sequence",
    [list("AAAAAA"), list("ABABAB"), list("ABCABC"), list("xyABABAB")],
)
def test_repeat_detector_catches_cycles_of_one_two_and_three(sequence: list[str]) -> None:
    from ensemble.quality import inspect_response

    codes = [f.code for f in inspect_response("x", sequence)]
    assert "repeated_tool_loop" in codes


@pytest.mark.parametrize("sequence", [list("ABCDEF"), list("AABBCC"), list("ABABAC"), list("ABAB")])
def test_repeat_detector_ignores_progress_and_short_sequences(sequence: list[str]) -> None:
    from ensemble.quality import inspect_response

    assert "repeated_tool_loop" not in [f.code for f in inspect_response("x", sequence)]
