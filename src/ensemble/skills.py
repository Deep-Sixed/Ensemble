from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillCard:
    name: str
    path: Path
    text: str


def default_skill_root() -> Path:
    """Locate Ensemble's own skill cards, independent of the current directory.

    Order: the copy packaged in the wheel (`ensemble/_skills`), an explicit
    ENSEMBLE_ROOT checkout, then the source checkout this package runs from
    (editable installs). The current directory is never consulted, so a project
    being worked on cannot supply its own cards.
    """
    packaged = Path(__file__).resolve().parent / "_skills"
    if packaged.is_dir():
        return packaged
    override = os.getenv("ENSEMBLE_ROOT")
    if override and (Path(override).expanduser() / "skills").is_dir():
        return Path(override).expanduser().resolve() / "skills"
    return Path(__file__).resolve().parents[2] / "skills"


def load_skill(path: str | Path) -> SkillCard:
    skill_path = Path(path)
    name = skill_path.parent.name if skill_path.name == "SKILL.md" else skill_path.stem
    return SkillCard(
        name=name,
        path=skill_path,
        text=skill_path.read_text(encoding="utf-8").strip(),
    )


def select_skill_paths(task: str, root: str | Path | None = None) -> list[Path]:
    text = task.lower()
    skill_root = Path(root) if root is not None else default_skill_root()
    selected: list[Path] = []

    rules = [
        ("", skill_root / "ensemble-technical" / "SKILL.md"),
        ("repo", skill_root / "repo-audit.md"),
        ("audit", skill_root / "repo-audit.md"),
        ("docker", skill_root / "docker-sandbox.md"),
        ("email", skill_root / "email-draft-polish" / "SKILL.md"),
        ("mail", skill_root / "email-draft-polish" / "SKILL.md"),
        ("draft", skill_root / "email-draft-polish" / "SKILL.md"),
        ("reply", skill_root / "email-draft-polish" / "SKILL.md"),
        ("outreach", skill_root / "email-draft-polish" / "SKILL.md"),
        ("patch", skill_root / "protocols" / "patch-proposal.md"),
        ("edit", skill_root / "protocols" / "patch-proposal.md"),
        ("implement", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("fix", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("bug", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("review", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("refactor", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("code", skill_root / "protocols" / "karpathy-guidelines.md"),
        ("write", skill_root / "tools" / "guarded-tools.md"),
        ("shell", skill_root / "tools" / "guarded-tools.md"),
        ("qwen", skill_root / "protocols" / "small-model-native-agent.md"),
        ("local", skill_root / "ensemble.md"),
    ]

    for keyword, path in rules:
        if (not keyword or keyword in text) and path.exists() and path not in selected:
            selected.append(path)

    if not selected and (skill_root / "ensemble.md").exists():
        selected.append(skill_root / "ensemble.md")

    return selected


def inject_skill_cards(task: str, root: str | Path | None = None) -> str:
    cards = [load_skill(path) for path in select_skill_paths(task, root)]
    if not cards:
        return ""

    rendered = ["Relevant Ensemble skill cards:"]
    for card in cards:
        rendered.append(f"\n[{card.name}]\n{_compact(card.text)}")
    return "\n".join(rendered)


def _compact(text: str, max_chars: int = 900) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
