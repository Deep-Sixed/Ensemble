from __future__ import annotations

import re
from dataclasses import dataclass

from ensemble.workspace import WorkspaceFile


_WORD = re.compile(r"[A-Za-z0-9_./-]+")


@dataclass(frozen=True)
class RankedFile:
    file: WorkspaceFile
    score: float
    reasons: tuple[str, ...]


def rank_files(task: str, files: list[WorkspaceFile]) -> list[RankedFile]:
    terms = {term.lower() for term in _WORD.findall(task) if len(term) > 1}
    ranked: list[RankedFile] = []

    for file in files:
        path_lower = file.relative_path.lower()
        stem_terms = set(_WORD.findall(path_lower))
        reasons: list[str] = []
        score = 0.0

        path_hits = sorted(term for term in terms if term in path_lower)
        if path_hits:
            score += 8.0 + 2.0 * len(path_hits)
            reasons.append("task term in path: " + ", ".join(path_hits[:5]))

        exact_name_hits = sorted(terms & stem_terms)
        if exact_name_hits:
            score += 4.0 * len(exact_name_hits)
            reasons.append("task term matches path token: " + ", ".join(exact_name_hits[:5]))

        if file.relative_path in {
            "README.md",
            "AGENTS.md",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
        }:
            score += 2.0
            reasons.append("repository guidance/manifest")

        if file.relative_path.startswith(("src/", "lib/", "app/")):
            score += 1.0
            reasons.append("source file")

        # Slightly prefer smaller files when relevance is otherwise equal.
        score += max(0.0, 1.0 - min(file.size_bytes, 100_000) / 100_000)

        ranked.append(RankedFile(file=file, score=round(score, 4), reasons=tuple(reasons)))

    ranked.sort(key=lambda item: (-item.score, item.file.relative_path))
    return ranked
