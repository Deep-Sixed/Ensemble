from __future__ import annotations

from pathlib import Path

import pytest

from ensemble.safety import SafetyError, WorkspaceGuard


def test_derived_paths_are_confined_to_ensemble_directory(tmp_path: Path) -> None:
    guard = WorkspaceGuard(tmp_path)
    assert guard.resolve_derived_path(".ensemble/symbols.jsonl") == (
        tmp_path / ".ensemble" / "symbols.jsonl"
    ).resolve()

    with pytest.raises(SafetyError):
        guard.resolve_derived_path("symbols.jsonl")


def test_read_path_rejects_workspace_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-ensemble-test.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        guard = WorkspaceGuard(tmp_path)
        with pytest.raises(SafetyError):
            guard.resolve_read_path(outside)
    finally:
        outside.unlink(missing_ok=True)
