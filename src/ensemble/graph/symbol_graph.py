from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

Json = dict[str, Any]


@dataclass(frozen=True)
class GraphFact:
    type: str
    id: str | None = None
    kind: str | None = None
    source: str | None = None
    target: str | None = None
    path: str | None = None
    name: str | None = None
    qualified_name: str | None = None
    symbol_kind: int | None = None

    def to_dict(self) -> Json:
        return {key: value for key, value in asdict(self).items() if value is not None}


def load_symbol_records(path: str | Path) -> list[Json]:
    records: list[Json] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records


def build_symbol_graph(symbol_records_path: str | Path) -> list[Json]:
    return build_symbol_graph_records(
        load_symbol_records(symbol_records_path),
        source=Path(symbol_records_path).name,
    )


def build_symbol_graph_records(records: list[Json], *, source: str = "context") -> list[Json]:
    facts: list[Json] = [
        {
            "type": "meta",
            "schema_version": 1,
            "source": source,
            "generated_by": "ensemble",
        }
    ]
    graph_facts: list[GraphFact] = []
    seen_nodes: set[str] = set()
    symbol_by_key = _symbol_lookup(records)

    for record in records:
        file_path = str(record["file_path"])
        symbol_id = _symbol_id(str(record["id"]))
        file_id = _file_id(file_path)

        if file_id not in seen_nodes:
            graph_facts.append(GraphFact(type="node", id=file_id, kind="file", path=file_path))
            seen_nodes.add(file_id)

        if symbol_id not in seen_nodes:
            graph_facts.append(
                GraphFact(
                    type="node",
                    id=symbol_id,
                    kind="symbol",
                    name=str(record["name"]),
                    qualified_name=str(record["qualified_name"]),
                    symbol_kind=int(record["kind"]),
                )
            )
            seen_nodes.add(symbol_id)

        graph_facts.append(
            GraphFact(
                type="edge",
                kind="file_contains_symbol",
                source=file_id,
                target=symbol_id,
            )
        )

        parent = _find_container_record(record, symbol_by_key)
        if parent is not None:
            graph_facts.append(
                GraphFact(
                    type="edge",
                    kind="container_contains_symbol",
                    source=_symbol_id(str(parent["id"])),
                    target=symbol_id,
                )
            )

    facts.extend(fact.to_dict() for fact in graph_facts)
    return facts


def write_symbol_graph(symbol_records_path: str | Path, out: str | Path) -> int:
    facts = build_symbol_graph(symbol_records_path)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as handle:
        for fact in facts:
            handle.write(json.dumps(fact, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    return len(facts)


def _file_id(file_path: str) -> str:
    return f"file:{file_path}"


def _symbol_id(symbol_record_id: str) -> str:
    return f"symbol:{symbol_record_id}"


def _symbol_lookup(records: list[Json]) -> dict[tuple[str, str], Json]:
    lookup: dict[tuple[str, str], Json] = {}
    for record in records:
        file_path = str(record["file_path"])
        lookup[(file_path, str(record["name"]))] = record
        lookup[(file_path, str(record["qualified_name"]))] = record
    return lookup


def _find_container_record(record: Json, lookup: dict[tuple[str, str], Json]) -> Json | None:
    container_name = record.get("container_name")
    if container_name is None:
        return None

    file_path = str(record["file_path"])
    parent = lookup.get((file_path, str(container_name)))
    if parent is not None:
        return parent

    suffix = f".{container_name}"
    for (candidate_file, candidate_name), candidate in lookup.items():
        if candidate_file == file_path and candidate_name.endswith(suffix):
            return candidate
    return None
