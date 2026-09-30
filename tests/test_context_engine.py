from __future__ import annotations

from pathlib import Path

from ensemble.budget import ContextBudget, estimate_tokens
from ensemble.context import build_context_packet
from ensemble.ranking import rank_files
from ensemble.safety import WorkspaceGuard
from ensemble.workspace import WorkspaceFile, discover_workspace_files


def test_budget_truncates_without_exceeding_limit() -> None:
    budget = ContextBudget(3)
    accepted, truncated = budget.take("abcdefghijklmnop")
    assert truncated is True
    assert estimate_tokens(accepted) <= 3
    assert budget.used == 3


def test_ranking_prefers_task_path_matches(tmp_path: Path) -> None:
    auth = tmp_path / "src" / "auth_timeout.py"
    other = tmp_path / "src" / "util.py"
    auth.parent.mkdir(parents=True)
    auth.write_text("def timeout(): pass\n", encoding="utf-8")
    other.write_text("def helper(): pass\n", encoding="utf-8")

    files = [
        WorkspaceFile(auth, "src/auth_timeout.py", auth.stat().st_size),
        WorkspaceFile(other, "src/util.py", other.stat().st_size),
    ]
    ranked = rank_files("fix auth timeout handling", files)
    assert ranked[0].file.relative_path == "src/auth_timeout.py"
    assert ranked[0].score > ranked[1].score


def test_workspace_discovery_excludes_generated_dirs_and_binary(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("secret-ish\n", encoding="utf-8")
    (tmp_path / "blob.bin").write_bytes(b"abc\x00def")

    guard = WorkspaceGuard(tmp_path)
    paths = [item.relative_path for item in discover_workspace_files(guard)]
    assert paths == ["src/main.py"]


def test_context_packet_is_structured_and_budgeted(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text(
        "def login_timeout():\n    return 30\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("Authentication service\n", encoding="utf-8")

    guard = WorkspaceGuard(tmp_path)
    packet = build_context_packet(
        "fix authentication timeout",
        guard,
        token_budget=100,
        skill_root=tmp_path / "missing-skills",
    )

    payload = packet.to_dict()
    assert payload["schema_version"] == 1
    assert payload["task"] == "fix authentication timeout"
    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["files"]
    assert payload["files"][0]["path"] in {"README.md", "src/auth.py"}
    assert payload["symbols"] == []
    assert payload["definitions"] == []
    assert payload["references"] == []
    assert payload["token_estimate"] <= 100
