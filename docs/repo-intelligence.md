# Repo Intelligence Artifacts

`.ensemble/symbols.jsonl`

Normalized symbol index. Produced from LSP document symbols. Source of truth for
symbol identity, file path, ownership, ranges, and content hash.

`.ensemble/symbol-graph.jsonl`

Derived graph facts. Produced from `symbols.jsonl`. Source of truth for
file/symbol nodes and containment edges.

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
