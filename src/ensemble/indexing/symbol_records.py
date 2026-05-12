from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

Json = dict[str, Any]


@dataclass(frozen=True)
class SymbolRecord:
    schema_version: int
    id: str
    identity_hash: str
    content_hash: str
    file_path: str
    name: str
    container_name: str | None
    qualified_name: str
    kind: int
    start_line: int
    start_character: int
    end_line: int
    end_character: int
    selection_start_line: int
    selection_start_character: int

    def to_dict(self) -> Json:
        return asdict(self)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def relative_file_path(repo_root: str | Path, file_path: str | Path) -> str:
    root = Path(repo_root).resolve()
    path = Path(file_path).resolve()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def qualified_name(name: str, container_name: str | None) -> str:
    return f"{container_name}.{name}" if container_name else name


def extract_snippet(
    file_path: str | Path,
    start_line: int,
    end_line: int,
    *,
    max_chars: int = 2000,
) -> str:
    path = Path(file_path)
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    if not lines:
        return ""

    start = max(start_line, 0)
    end = min(max(end_line + 1, start + 1), len(lines))
    snippet = "\n".join(lines[start:end]).strip()
    if len(snippet) > max_chars:
        return snippet[: max_chars - 3].rstrip() + "..."
    return snippet


def build_symbol_record(
    *,
    repo_root: str | Path,
    absolute_file_path: str | Path,
    symbol: Json,
    schema_version: int = 1,
) -> SymbolRecord:
    rel_path = relative_file_path(repo_root, absolute_file_path)
    name = str(symbol["name"])
    container_name_raw = symbol.get("container_name")
    container_name = str(container_name_raw) if container_name_raw is not None else None
    kind = int(symbol["kind"])
    start_line = int(symbol["start_line"])
    start_character = int(symbol["start_character"])
    end_line = int(symbol["end_line"])
    end_character = int(symbol["end_character"])
    selection_start_line = int(symbol.get("selection_start_line", start_line))
    selection_start_character = int(symbol.get("selection_start_character", start_character))
    qname = qualified_name(name, container_name)
    snippet = extract_snippet(absolute_file_path, start_line, end_line)

    identity_hash = sha256_text(
        "|".join(
            [
                str(Path(repo_root).resolve()),
                rel_path,
                container_name or "",
                name,
                str(kind),
            ]
        )
    )
    content_hash = sha256_text(snippet)
    record_id = sha256_text(
        "|".join(
            [
                identity_hash,
                str(selection_start_line),
                str(selection_start_character),
                content_hash,
            ]
        )
    )

    return SymbolRecord(
        schema_version=schema_version,
        id=record_id,
        identity_hash=identity_hash,
        content_hash=content_hash,
        file_path=rel_path,
        name=name,
        container_name=container_name,
        qualified_name=qname,
        kind=kind,
        start_line=start_line,
        start_character=start_character,
        end_line=end_line,
        end_character=end_character,
        selection_start_line=selection_start_line,
        selection_start_character=selection_start_character,
    )
