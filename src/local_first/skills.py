from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SkillCard:
    name: str
    path: Path
    text: str


def load_skill(path: str | Path) -> SkillCard:
    skill_path = Path(path)
    return SkillCard(
        name=skill_path.stem,
        path=skill_path,
        text=skill_path.read_text(encoding="utf-8").strip(),
    )


def select_skill_paths(task: str, root: str | Path = "skills") -> list[Path]:
    text = task.lower()
    skill_root = Path(root)
    selected: list[Path] = []

    rules = [
        ("repo", skill_root / "repo-audit.md"),
        ("audit", skill_root / "repo-audit.md"),
        ("docker", skill_root / "docker-sandbox.md"),
        ("patch", skill_root / "protocols" / "patch-proposal.md"),
        ("edit", skill_root / "protocols" / "patch-proposal.md"),
        ("write", skill_root / "tools" / "guarded-tools.md"),
        ("shell", skill_root / "tools" / "guarded-tools.md"),
        ("qwen", skill_root / "protocols" / "small-model-native-agent.md"),
        ("local", skill_root / "local-first.md"),
    ]

    for keyword, path in rules:
        if keyword in text and path.exists() and path not in selected:
            selected.append(path)

    if not selected and (skill_root / "local-first.md").exists():
        selected.append(skill_root / "local-first.md")

    return selected


def inject_skill_cards(task: str, root: str | Path = "skills") -> str:
    cards = [load_skill(path) for path in select_skill_paths(task, root)]
    if not cards:
        return ""

    rendered = ["Relevant Local-First skill cards:"]
    for card in cards:
        rendered.append(f"\n[{card.name}]\n{_compact(card.text)}")
    return "\n".join(rendered)


def _compact(text: str, max_chars: int = 900) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."
