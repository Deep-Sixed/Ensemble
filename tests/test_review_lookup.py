from __future__ import annotations

import json
from pathlib import Path

from ensemble.review import ImpactAnalysis, SymbolLookup


def test_symbol_lookup_indexes_files_qualified_names_and_children(tmp_path: Path) -> None:
    symbols_path, graph_path = _write_fixtures(tmp_path)

    lookup = SymbolLookup.from_files(symbols_path, graph_path)

    file_symbols = lookup.symbols_in_file("src/pkg/foo.py")
    assert [symbol["qualified_name"] for symbol in file_symbols] == [
        "Foo",
        "Foo.bar",
        "Foo.baz",
    ]

    assert lookup.symbol_by_qualified_name("src/pkg/foo.py", "Foo.bar") == _symbol(
        "bar-id",
        "src/pkg/foo.py",
        "bar",
        "Foo",
        "Foo.bar",
        6,
        3,
        4,
    )

    assert [
        symbol["qualified_name"] for symbol in lookup.children_of_symbol("symbol:foo-id")
    ] == ["Foo.bar", "Foo.baz"]


def test_impact_analysis_returns_declared_symbols_and_children(tmp_path: Path) -> None:
    symbols_path, graph_path = _write_fixtures(tmp_path)
    analysis = ImpactAnalysis.from_files(symbols_path, graph_path)

    impacted = analysis.symbols_impacted_by_change("src/pkg/foo.py")

    assert [symbol["id"] for symbol in impacted] == ["foo-id", "bar-id", "baz-id"]
    assert [symbol["qualified_name"] for symbol in impacted] == [
        "Foo",
        "Foo.bar",
        "Foo.baz",
    ]


def _write_fixtures(tmp_path: Path) -> tuple[Path, Path]:
    symbols = [
        _symbol("foo-id", "src/pkg/foo.py", "Foo", None, "Foo", 5, 1, 0),
        _symbol("bar-id", "src/pkg/foo.py", "bar", "Foo", "Foo.bar", 6, 3, 4),
        _symbol("baz-id", "src/pkg/foo.py", "baz", "Foo", "Foo.baz", 6, 8, 4),
        _symbol("other-id", "src/pkg/other.py", "Other", None, "Other", 5, 1, 0),
    ]
    graph = [
        {"type": "meta", "schema_version": 1},
        {
            "type": "edge",
            "kind": "container_contains_symbol",
            "source": "symbol:foo-id",
            "target": "symbol:bar-id",
        },
        {
            "type": "edge",
            "kind": "container_contains_symbol",
            "source": "symbol:foo-id",
            "target": "symbol:baz-id",
        },
        {
            "type": "edge",
            "kind": "file_contains_symbol",
            "source": "file:src/pkg/foo.py",
            "target": "symbol:foo-id",
        },
    ]

    symbols_path = tmp_path / "symbols.jsonl"
    graph_path = tmp_path / "symbol-graph.jsonl"
    _write_jsonl(symbols_path, symbols)
    _write_jsonl(graph_path, graph)
    return symbols_path, graph_path


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _symbol(
    symbol_id: str,
    file_path: str,
    name: str,
    container_name: str | None,
    qualified_name: str,
    kind: int,
    start_line: int,
    start_character: int,
) -> dict:
    return {
        "schema_version": 1,
        "id": symbol_id,
        "identity_hash": f"identity-{symbol_id}",
        "content_hash": f"content-{symbol_id}",
        "file_path": file_path,
        "name": name,
        "container_name": container_name,
        "qualified_name": qualified_name,
        "kind": kind,
        "start_line": start_line,
        "start_character": start_character,
        "end_line": start_line + 1,
        "end_character": 0,
        "selection_start_line": start_line,
        "selection_start_character": start_character,
    }
