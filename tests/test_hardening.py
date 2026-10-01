from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from ensemble.config import load_config
from ensemble.safety import SafetyError, WorkspaceGuard
from ensemble.session import Session
from ensemble.tools.coding import coding_tools
from ensemble.tools.filesystem import list_files


def tools(ws: Path, **kw) -> dict:
    guard = WorkspaceGuard(ws, allow_writes=True, allow_shell=True)
    return {t.name: t for t in coding_tools(guard, ws / ".ensemble" / "checkpoints")}


@pytest.mark.parametrize("path", [".git/config", "sub/.git/config", ".ensemble/sessions/x.jsonl"])
def test_writes_to_git_and_ensemble_dirs_are_refused(tmp_path: Path, path: str) -> None:
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_text("[core]\n")
    t = tools(tmp_path)
    with pytest.raises(SafetyError, match="protected"):
        t["edit"].run({"path": path, "old_text": "[core]", "new_text": "[core]\nfsmonitor=x"})
    with pytest.raises(SafetyError, match="protected"):
        t["write"].run({"path": path + ".new", "content": "x"})
    assert target.read_text() == "[core]\n"


def test_nested_ensemble_name_is_not_protected(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path, allow_writes=True)
    assert guard.resolve_write_path("docs/.ensemble/notes.md")


def test_bash_does_not_inherit_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENSEMBLE_API_KEY", "sekret")
    out = tools(tmp_path)["bash"].run({"command": "echo key=[$ENSEMBLE_API_KEY]; echo ok"})
    assert "key=[]" in out and "sekret" not in out


def test_bash_output_is_bounded_and_returns_after_kill(tmp_path: Path) -> None:
    out = tools(tmp_path)["bash"].run({"command": "yes", "timeout": 1})
    assert "Timed out" in out and "Output truncated" in out
    assert len(out) < 200_000


def test_edit_preserves_crlf_and_matches_lf_old_text(tmp_path: Path) -> None:
    (tmp_path / "c.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    tools(tmp_path)["edit"].run({"path": "c.txt", "old_text": "one\ntwo", "new_text": "1\n2"})
    assert (tmp_path / "c.txt").read_bytes() == b"1\r\n2\r\nthree\r\n"


def test_edit_leaves_lf_files_alone(tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_bytes(b"a\nb\n")
    tools(tmp_path)["edit"].run({"path": "f.txt", "old_text": "b", "new_text": "B"})
    assert (tmp_path / "f.txt").read_bytes() == b"a\nB\n"


def test_list_files_works_under_a_build_directory(tmp_path: Path) -> None:
    ws = tmp_path / "build" / "proj"
    (ws / "node_modules" / "pkg").mkdir(parents=True)
    (ws / "node_modules" / "pkg" / "i.js").write_text("")
    (ws / "src").mkdir()
    (ws / "src" / "a.py").write_text("")
    assert list_files(WorkspaceGuard(ws)) == ["src", "src/a.py"]


def test_list_files_honors_limit_and_does_not_descend_skipped(tmp_path: Path) -> None:
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("")
    assert len(list_files(WorkspaceGuard(tmp_path), limit=3)) == 3


def _profile_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, temperature: float, tokens: int):
    import ensemble.profiles as profiles

    profile = profiles.ModelProfile(
        name="p", provider="local", model="m", base_url="http://x/v1",
        api_key_env="ENSEMBLE_TEST_KEY", context_window=4096, max_tokens=tokens,
        temperature=temperature, reasoning=False, cost={},
    )
    monkeypatch.setattr(profiles, "load_named_profile", lambda name: profile)
    monkeypatch.setenv("ENSEMBLE_WORKSPACE", str(tmp_path))
    for var in ("ENSEMBLE_TEMPERATURE", "ENSEMBLE_MAX_TOKENS", "ENSEMBLE_PROFILE"):
        monkeypatch.delenv(var, raising=False)


def test_profile_temperature_zero_is_respected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _profile_env(monkeypatch, tmp_path, 0.0, 512)
    assert load_config(env_file=tmp_path / "none.env", profile_override="p").temperature == 0.0
    monkeypatch.setenv("ENSEMBLE_PROFILE", "p")
    cfg = load_config(env_file=tmp_path / "none.env")
    assert cfg.temperature == 0.0 and cfg.max_tokens == 512


def test_session_survives_torn_write_and_appends_cleanly(tmp_path: Path) -> None:
    session = Session(tmp_path / "s.jsonl")
    session.append({"role": "user", "content": "hi"})
    with session.path.open("a") as handle:
        handle.write('{"role": "assist')  # crash mid-write, no newline
    assert session.load() == [{"role": "user", "content": "hi"}]
    session.append({"role": "user", "content": "again"})
    assert [m["content"] for m in session.load()] == ["hi", "again"]


def test_session_drops_tool_calls_without_results(tmp_path: Path) -> None:
    session = Session(tmp_path / "s.jsonl")
    call = lambda i: {"id": i, "type": "function", "function": {"name": "read", "arguments": "{}"}}  # noqa: E731
    for message in [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "", "tool_calls": [call("a")]},
        {"role": "tool", "tool_call_id": "a", "content": "ok"},
        {"role": "assistant", "content": "", "tool_calls": [call("b")]},  # interrupted
        {"role": "user", "content": "retry"},
    ]:
        session.append(message)
    loaded = session.load()
    assert [m["role"] for m in loaded] == ["user", "assistant", "tool", "user"]
    assert json.dumps(loaded).count('"id": "b"') == 0


# --- findings 7-10 ---


def test_fit_history_elides_old_tool_output_but_not_stored_history() -> None:
    from ensemble.harness import fit_history

    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "type": "function", "function": {"name": "read", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "a", "content": "x" * 5000},
        {"role": "user", "content": "two"},
    ]
    fitted = fit_history(history, 1000)
    assert "elided" in fitted[2]["content"] and fitted[-1]["content"] == "two"
    assert history[2]["content"] == "x" * 5000


def test_fit_history_drops_whole_turns_and_keeps_latest_prompt() -> None:
    from ensemble.harness import fit_history

    history = []
    for i in range(10):
        history += [{"role": "user", "content": f"q{i}" + "y" * 500}, {"role": "assistant", "content": "a" * 500}]
    history.append({"role": "user", "content": "latest"})
    fitted = fit_history(history, 1500)
    assert fitted[0]["role"] == "user" and fitted[-1]["content"] == "latest"
    assert len(fitted) < len(history)


def test_fit_history_passes_small_history_through() -> None:
    from ensemble.harness import fit_history

    history = [{"role": "user", "content": "hi"}]
    assert fit_history(history, 10_000) == history


def test_checkpoint_names_do_not_collide_or_glob(tmp_path: Path) -> None:
    from ensemble.checkpoints import create_checkpoint, has_checkpoint

    guard = WorkspaceGuard(tmp_path)
    for name in ("a/b.py", "a__b.py", "x[1].py"):
        (tmp_path / name).parent.mkdir(exist_ok=True)
        (tmp_path / name).write_text(name)
    root = tmp_path / "cp"
    create_checkpoint(guard, "a/b.py", root)
    assert has_checkpoint(guard, "a/b.py", root)
    assert not has_checkpoint(guard, "a__b.py", root)
    assert not has_checkpoint(guard, "x[1].py", root)
    create_checkpoint(guard, "x[1].py", root)
    assert has_checkpoint(guard, "x[1].py", root)


def test_loop_detector_resets_between_prompts(tmp_path: Path) -> None:
    from ensemble.harness import Agent
    from ensemble.llm import AssistantTurn, ToolCall
    from test_harness import ScriptedClient, make_config

    (tmp_path / "f.txt").write_text("x")

    def turns() -> list[AssistantTurn]:
        calls = [AssistantTurn(tool_calls=[ToolCall(f"c{i}", "read", '{"path": "f.txt"}')]) for i in range(3)]
        return calls + [AssistantTurn(content="done")]

    client = ScriptedClient(*turns(), *turns())
    agent = Agent(make_config(tmp_path), client=client)
    assert agent.run("first") == "done"
    assert agent.run("second") == "done"  # was stopped as a "loop" by the first prompt's calls


def test_default_workspace_is_cwd_not_a_host_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ensemble.paths import default_workspace

    monkeypatch.delenv("ENSEMBLE_WORKSPACE", raising=False)
    monkeypatch.chdir(tmp_path)
    assert default_workspace() == tmp_path.resolve()
    monkeypatch.setenv("ENSEMBLE_WORKSPACE", str(tmp_path / "other"))
    assert default_workspace() == tmp_path / "other"
