from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ensemble.review.symbol_lookup import SymbolLookup


@dataclass(frozen=True)
class ImpactAnalysis:
    lookup: SymbolLookup

    @classmethod
    def from_files(cls, symbols_path: str | Path, graph_path: str | Path) -> "ImpactAnalysis":
        return cls(SymbolLookup.from_files(symbols_path, graph_path))

    def symbols_impacted_by_change(self, file_path: str) -> list[dict]:
        impacted: dict[str, dict] = {}
        for symbol in self.lookup.symbols_in_file(file_path):
            symbol_id = str(symbol["id"])
            impacted[symbol_id] = symbol
            for child in self.lookup.children_of_symbol(symbol_id):
                impacted[str(child["id"])] = child

        return sorted(
            impacted.values(),
            key=lambda item: (
                str(item.get("file_path", "")),
                int(item.get("start_line", 0)),
                int(item.get("start_character", 0)),
                str(item.get("qualified_name", "")),
            ),
        )
