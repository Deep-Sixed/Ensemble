from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ensemble.indexing.symbol_records import SymbolRecord, build_symbol_record
from ensemble.lsp_client import LspServerManager, flatten_document_symbols

DEFAULT_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


def iter_indexable_files(
    root: str | Path,
    manager: LspServerManager,
    *,
    excludes: set[str] | None = None,
) -> Iterable[Path]:
    root_path = Path(root).resolve()
    excluded = excludes or DEFAULT_EXCLUDES

    if root_path.is_file():
        if manager.config_for_file(root_path) is not None:
            yield root_path
        return

    for path in sorted(root_path.rglob("*")):
        if not path.is_file():
            continue
        if any(part in excluded for part in path.parts):
            continue
        if manager.config_for_file(path) is None:
            continue
        yield path


async def index_symbols(
    root: str | Path,
    *,
    repo_root: str | Path | None = None,
    manager: LspServerManager | None = None,
) -> list[SymbolRecord]:
    owns_manager = manager is None
    active_manager = manager or LspServerManager()
    root_path = Path(root).resolve()
    records: list[SymbolRecord] = []

    try:
        effective_repo_root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else active_manager.find_workspace_root(root_path)
        )

        for file_path in iter_indexable_files(root_path, active_manager):
            symbols = await active_manager.document_symbols(file_path)
            flat_symbols = flatten_document_symbols(symbols)

            for symbol in flat_symbols:
                if "name" not in symbol or "kind" not in symbol:
                    continue

                records.append(
                    build_symbol_record(
                        repo_root=effective_repo_root,
                        absolute_file_path=file_path,
                        symbol=symbol,
                    )
                )

        records.sort(
            key=lambda item: (
                item.file_path,
                item.start_line,
                item.start_character,
                item.qualified_name,
            )
        )
        return records
    finally:
        if owns_manager:
            await active_manager.close_all()


async def write_symbol_index(
    root: str | Path,
    out: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> int:
    records = await index_symbols(root, repo_root=repo_root)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    return len(records)
