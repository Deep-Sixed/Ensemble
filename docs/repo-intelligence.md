# Repo Intelligence Artifacts

`.ensemble/symbols.jsonl`

Normalized symbol index. Produced from LSP document symbols. Source of truth for
symbol identity, file path, ownership, ranges, and content hash.

`.ensemble/symbol-graph.jsonl`

Derived graph facts. Produced from `symbols.jsonl`. Source of truth for
file/symbol nodes and containment edges.

Both files are written by the CLI:

```bash
ensemble symbols index <path>        # -> .ensemble/symbols.jsonl (needs an LSP server)
ensemble graph symbols .ensemble/symbols.jsonl   # -> .ensemble/symbol-graph.jsonl
```

`SymbolLookup` and `ImpactAnalysis` live in `src/ensemble/review/`
(`symbol_lookup.py`, `impact_analysis.py`) and load both files via
`from_files(symbols_path, graph_path)`.

## Boundary Rule

Anything above JSONL must not depend on:

- LSP
- Pyright subprocesses
- model calls
- editor state

Anything below JSONL may be:

- live
- runtime-specific
- tool-specific

## Pipeline

```text
Pyright/LSP
  -> .ensemble/symbols.jsonl
  -> .ensemble/symbol-graph.jsonl
  -> SymbolLookup
  -> ImpactAnalysis
```
