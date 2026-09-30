from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from ensemble.budget import ContextBudget, estimate_tokens
from ensemble.context import ContextPacket, build_context_packet
from ensemble.graph.symbol_graph import build_symbol_graph_records
from ensemble.indexing.symbol_index import index_symbols
from ensemble.lsp_client import LspLocation, LspServerManager
from ensemble.review import ImpactAnalysis, SymbolLookup
from ensemble.safety import WorkspaceGuard


_WORD = re.compile(r"[A-Za-z0-9_./-]+")


async def build_semantic_context_packet(
    task: str,
    guard: WorkspaceGuard,
    *,
    token_budget: int = 12_000,
    max_file_bytes: int = 200_000,
    max_files: int = 40,
    skill_root: str | Path = "skills",
    max_symbols: int = 30,
    max_navigation_symbols: int = 8,
) -> ContextPacket:
    packet = build_context_packet(
        task,
        guard,
        token_budget=token_budget,
        max_file_bytes=max_file_bytes,
        max_files=max_files,
        skill_root=skill_root,
    )

    manager = LspServerManager()
    symbol_records: list[dict[str, Any]] = []
    try:
        for file_info in packet.files:
            absolute = guard.resolve_read_path(str(file_info["path"]))
            if manager.config_for_file(absolute) is None:
                continue
            try:
                records = await index_symbols(
                    absolute,
                    repo_root=guard.root,
                    manager=manager,
                )
            except Exception:
                continue
            symbol_records.extend(record.to_dict() for record in records)

        ranked_symbols = rank_symbol_records(task, symbol_records)[:max_symbols]
        graph_facts = build_symbol_graph_records(symbol_records, source="ensemble context")
        lookup = SymbolLookup(symbol_records, graph_facts)
        impact = ImpactAnalysis(lookup)

        # Expand structurally related symbols for selected files.
        expanded: dict[str, dict[str, Any]] = {str(item["id"]): item for item in ranked_symbols}
        for file_info in packet.files[:10]:
            for item in impact.symbols_impacted_by_change(str(file_info["path"])):
                expanded.setdefault(str(item["id"]), item)
        symbols = rank_symbol_records(task, list(expanded.values()))[:max_symbols]

        definitions: list[dict[str, Any]] = []
        references: list[dict[str, Any]] = []
        for symbol in symbols[:max_navigation_symbols]:
            absolute = guard.resolve_read_path(str(symbol["file_path"]))
            line = int(symbol.get("selection_start_line", symbol.get("start_line", 0)))
            character = int(symbol.get("selection_start_character", symbol.get("start_character", 0)))

            try:
                defs = await manager.definition(absolute, line, character)
            except Exception:
                defs = []
            if defs:
                definitions.append(
                    {
                        "symbol": str(symbol["qualified_name"]),
                        "locations": [_location_to_dict(item, guard.root) for item in defs],
                    }
                )

            try:
                refs = await manager.references(absolute, line, character)
            except Exception:
                refs = []
            if refs:
                references.append(
                    {
                        "symbol": str(symbol["qualified_name"]),
                        "locations": [_location_to_dict(item, guard.root) for item in refs[:50]],
                    }
                )
    finally:
        await manager.close_all()

    semantic_text = _render_semantic_context(symbols, definitions, references)
    remaining = max(0, packet.token_budget - estimate_tokens(packet.context))
    truncated = packet.truncated
    context = packet.context

    if semantic_text and remaining > 0:
        semantic_budget = ContextBudget(remaining)
        accepted, semantic_truncated = semantic_budget.take(semantic_text)
        if accepted:
            context = f"{context}\n\n[semantic]\n{accepted}" if context else f"[semantic]\n{accepted}"
        truncated = truncated or semantic_truncated
    elif semantic_text:
        truncated = True

    return replace(
        packet,
        symbols=symbols,
        definitions=definitions,
        references=references,
        context=context,
        token_estimate=estimate_tokens(context),
        truncated=truncated,
    )


def rank_symbol_records(task: str, symbols: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = {term.lower() for term in _WORD.findall(task) if len(term) > 1}

    def score(symbol: dict[str, Any]) -> tuple[float, str, int, str]:
        name = str(symbol.get("qualified_name") or symbol.get("name") or "").lower()
        path = str(symbol.get("file_path", "")).lower()
        value = 0.0
        for term in terms:
            if term in name:
                value += 5.0
            if term in path:
                value += 2.0
        return (
            -value,
            path,
            int(symbol.get("start_line", 0)),
            name,
        )

    return sorted(symbols, key=score)


def _location_to_dict(location: LspLocation, root: Path) -> dict[str, Any]:
    payload = location.to_dict()
    raw_path = Path(str(payload.get("file_path", "")))
    try:
        payload["file_path"] = raw_path.resolve().relative_to(root).as_posix()
    except (OSError, ValueError):
        payload["file_path"] = raw_path.as_posix()
    return payload


def _render_semantic_context(
    symbols: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    if symbols:
        lines.append("symbols:")
        for symbol in symbols:
            lines.append(
                f"- {symbol['file_path']}:{int(symbol['start_line']) + 1} "
                f"{symbol['qualified_name']}"
            )
    if definitions:
        lines.append("definitions:")
        for item in definitions:
            lines.append(f"- {item['symbol']}: {len(item['locations'])} location(s)")
    if references:
        lines.append("references:")
        for item in references:
            lines.append(f"- {item['symbol']}: {len(item['locations'])} location(s)")
    return "\n".join(lines)
