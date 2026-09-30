from __future__ import annotations

import re
from dataclasses import dataclass

from ensemble.workspace import WorkspaceFile


_WORD = re.compile(r"[A-Za-z0-9_./-]+")
_ALNUM = re.compile(r"[A-Za-z0-9]+")
_SUBWORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")

# Generic task verbs/fillers that carry no signal about which code matters.
_STOPWORDS = {
    "a", "add", "all", "an", "and", "are", "as", "at", "be", "by", "can", "change",
    "code", "does", "file", "files", "fix", "for", "from", "get", "how", "in", "into",
    "is", "it", "make", "new", "not", "of", "on", "or", "remove", "set", "should",
    "so", "that", "the", "this", "to", "update", "use", "when", "where", "why",
    "with",
}

# Bytes of each file scanned for identifier matches. Files are already capped by
# ENSEMBLE_MAX_FILE_BYTES during discovery; this keeps ranking cheap regardless.
MAX_CONTENT_SCAN_BYTES = 256_000
_STEM_CHARS = 6


@dataclass(frozen=True)
class RankedFile:
    file: WorkspaceFile
    score: float
    reasons: tuple[str, ...]


def rank_files(
    task: str,
    files: list[WorkspaceFile],
    *,
    changed_paths: set[str] | None = None,
    scan_content: bool = True,
) -> list[RankedFile]:
    terms = {
        term
        for term in (raw.lower() for raw in _WORD.findall(task))
        if len(term) > 1 and term not in _STOPWORDS
    }
    content_terms = task_content_terms(task)
    changed = changed_paths or set()
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

        if scan_content and content_terms:
            content_hits = _content_hits(content_terms, file)
            if content_hits:
                score += 3.0 * len(content_hits)
                reasons.append("task term in content: " + ", ".join(content_hits[:5]))

        if file.relative_path in changed:
            score += 3.0
            reasons.append("changed in working tree")

        if file.relative_path.startswith(("src/", "lib/", "app/")):
            score += 1.0
            reasons.append("source file")

        # Slightly prefer smaller files when relevance is otherwise equal.
        score += max(0.0, 1.0 - min(file.size_bytes, 100_000) / 100_000)

        ranked.append(RankedFile(file=file, score=round(score, 4), reasons=tuple(reasons)))

    ranked.sort(key=lambda item: (-item.score, item.file.relative_path))
    return ranked


def task_content_terms(task: str) -> set[str]:
    """Lower-cased identifier sub-words from the task, minus generic filler words."""
    return {
        word
        for word in _subwords(task)
        if len(word) >= 3 and word not in _STOPWORDS
    }


def _subwords(text: str) -> set[str]:
    words: set[str] = set()
    for token in _ALNUM.findall(text):
        for part in _SUBWORD.findall(token):
            words.add(part.lower())
    return words


def _stem(word: str) -> str:
    return word[:_STEM_CHARS]


def _content_hits(terms: set[str], file: WorkspaceFile) -> list[str]:
    try:
        with file.path.open("rb") as handle:
            raw = handle.read(MAX_CONTENT_SCAN_BYTES)
    except OSError:
        return []
    # Every stem plus its 4+ character prefixes, so "auth" matches "authenticate"
    # and "authentication" matches "authenticator" with plain set lookups.
    prefixes: set[str] = set()
    for word in _subwords(raw.decode("utf-8", errors="ignore")):
        stem = _stem(word)
        prefixes.add(stem)
        prefixes.update(stem[:size] for size in range(4, len(stem)))

    return [term for term in sorted(terms) if _stem(term) in prefixes]
