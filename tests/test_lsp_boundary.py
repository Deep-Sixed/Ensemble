from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ensemble.lsp_client import LspClient, LspLocation, LspServerManager
from ensemble.semantic import _location_to_dict, _navigation_entry


def _repo_with_nested_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    allowed = repo / "allowed"
    (repo / ".git").mkdir(parents=True)
    (repo / "secret").mkdir()
    allowed.mkdir()
    source = allowed / "main.py"
    source.write_text("def main():\n    return 1\n", encoding="utf-8")
    return repo, allowed, source


def test_root_discovery_never_climbs_above_max_root(tmp_path: Path) -> None:
    repo, allowed, source = _repo_with_nested_workspace(tmp_path)

    unbounded = LspServerManager()
    assert unbounded.find_workspace_root(source) == repo.resolve()

    bounded = LspServerManager(max_root=allowed)
    assert bounded.find_workspace_root(source) == allowed.resolve()


def test_root_discovery_uses_markers_inside_max_root(tmp_path: Path) -> None:
    _, allowed, _ = _repo_with_nested_workspace(tmp_path)
    package = allowed / "pkg"
    package.mkdir()
    (package / "pyproject.toml").write_text("[project]\nname='pkg'\n", encoding="utf-8")
    source = package / "mod.py"
    source.write_text("x = 1\n", encoding="utf-8")

    manager = LspServerManager(max_root=allowed)
    assert manager.find_workspace_root(source) == package.resolve()


def test_root_discovery_rejects_files_outside_max_root(tmp_path: Path) -> None:
    repo, allowed, _ = _repo_with_nested_workspace(tmp_path)
    outside = repo / "secret" / "keys.py"
    outside.write_text("KEY = 'x'\n", encoding="utf-8")

    manager = LspServerManager(max_root=allowed)
    with pytest.raises(ValueError):
        manager.find_workspace_root(outside)


def test_language_server_is_launched_with_bounded_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, allowed, source = _repo_with_nested_workspace(tmp_path)
    launched_roots: list[Path] = []

    async def fake_start(self: LspClient) -> None:
        launched_roots.append(self.root)

    monkeypatch.setattr(LspClient, "start", fake_start)
    monkeypatch.setattr(LspClient, "is_running", property(lambda self: True))

    async def run() -> None:
        manager = LspServerManager(max_root=allowed)
        client = await manager.get_client(source)
        assert client is not None
        manager._clients.clear()

    asyncio.run(run())
    assert launched_roots == [allowed.resolve()]


def _location(path: Path) -> LspLocation:
    return LspLocation(
        uri=path.resolve().as_uri(),
        start_line=1,
        start_character=0,
        end_line=1,
        end_character=4,
    )


def test_external_lsp_locations_are_not_emitted(tmp_path: Path) -> None:
    _, allowed, source = _repo_with_nested_workspace(tmp_path)
    outside = tmp_path / "other-project" / "lib.py"
    outside.parent.mkdir()
    outside.write_text("pass\n", encoding="utf-8")

    assert _location_to_dict(_location(outside), allowed.resolve()) is None

    entry = _navigation_entry(
        {"qualified_name": "main"},
        [_location(source), _location(outside)],
        allowed.resolve(),
    )
    assert entry["external_locations"] == 1
    assert [item["file_path"] for item in entry["locations"]] == ["main.py"]
    assert str(tmp_path) not in repr(entry)
