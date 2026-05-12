from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def load_symbols_jsonl(path: str | Path) -> list[Json]:
    return _load_jsonl(path)


def load_graph_jsonl(path: str | Path) -> list[Json]:
    return _load_jsonl(path)


@dataclass(frozen=True)
class SymbolLookup:
    symbols: list[Json]
    graph_facts: list[Json]
    by_id: dict[str, Json] = field(init=False, repr=False)
    by_file: dict[str, list[Json]] = field(init=False, repr=False)
    by_file_and_qualified_name: dict[tuple[str, str], Json] = field(init=False, repr=False)
    children_by_symbol_id: dict[str, list[Json]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        by_id: dict[str, Json] = {}
        by_file: dict[str, list[Json]] = defaultdict(list)
        by_file_and_qualified_name: dict[tuple[str, str], Json] = {}

        for symbol in self.symbols:
            symbol_id = str(symbol["id"])
            file_path = _normalize_path(str(symbol["file_path"]))
            qualified_name = str(symbol["qualified_name"])

            by_id[symbol_id] = symbol
            by_file[file_path].append(symbol)
            by_file_and_qualified_name[(file_path, qualified_name)] = symbol

        for symbol_list in by_file.values():
            symbol_list.sort(
                key=lambda item: (
                    int(item["start_line"]),
                    int(item["start_character"]),
                    str(item["qualified_name"]),
                )
            )

        children_by_symbol_id: dict[str, list[Json]] = defaultdict(list)
        for fact in self.graph_facts:
            if fact.get("type") != "edge":
                continue
            if fact.get("kind") != "container_contains_symbol":
                continue

            parent_id = _strip_symbol_prefix(str(fact["source"]))
            child_id = _strip_symbol_prefix(str(fact["target"]))
            child = by_id.get(child_id)
            if child is not None:
                children_by_symbol_id[parent_id].append(child)

        for children in children_by_symbol_id.values():
            children.sort(
                key=lambda item: (
                    str(item["file_path"]),
                    int(item["start_line"]),
                    int(item["start_character"]),
                    str(item["qualified_name"]),
                )
            )

        object.__setattr__(self, "by_id", by_id)
        object.__setattr__(self, "by_file", dict(by_file))
        object.__setattr__(
            self,
            "by_file_and_qualified_name",
            by_file_and_qualified_name,
        )
        object.__setattr__(self, "children_by_symbol_id", dict(children_by_symbol_id))

    @classmethod
    def from_files(cls, symbols_path: str | Path, graph_path: str | Path) -> "SymbolLookup":
        return cls(
            symbols=load_symbols_jsonl(symbols_path),
            graph_facts=load_graph_jsonl(graph_path),
        )

    def symbols_in_file(self, file_path: str) -> list[Json]:
        return list(self.by_file.get(_normalize_path(file_path), []))

    def children_of_symbol(self, symbol_id: str) -> list[Json]:
        return list(self.children_by_symbol_id.get(_strip_symbol_prefix(symbol_id), []))

    def symbol_by_qualified_name(self, file_path: str, qualified_name: str) -> Json | None:
        return self.by_file_and_qualified_name.get(
            (_normalize_path(file_path), qualified_name)
        )


def _load_jsonl(path: str | Path) -> list[Json]:
    records: list[Json] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def _normalize_path(file_path: str) -> str:
    return Path(file_path).as_posix()


def _strip_symbol_prefix(symbol_id: str) -> str:
    if symbol_id.startswith("symbol:"):
        return symbol_id.removeprefix("symbol:")
    return symbol_id
