from __future__ import annotations

import os
from pathlib import Path

import pytest

from ensemble.skills import default_skill_root, inject_skill_cards, select_skill_paths


def test_default_skill_root_does_not_depend_on_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = default_skill_root()
    assert root.is_absolute()
    assert (root / "ensemble-technical" / "SKILL.md").is_file()
    assert Path(os.getcwd()) not in root.parents

    rendered = inject_skill_cards("review this patch")
    assert "Relevant Ensemble skill cards:" in rendered


def test_non_code_skills_are_not_injected() -> None:
    selected = select_skill_paths("Fix the confidence decay pattern in this email draft ranking")
    names = {path.parent.name if path.name == "SKILL.md" else path.stem for path in selected}
    assert "learning-systems" not in names
    assert "email-draft-polish" not in names


def test_explicit_skill_root_overrides_bundled_cards(tmp_path: Path) -> None:
    (tmp_path / "ensemble.md").write_text("# Custom\n", encoding="utf-8")
    assert select_skill_paths("anything", tmp_path) == [tmp_path / "ensemble.md"]
