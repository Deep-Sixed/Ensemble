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

## Commands

```bash
ensemble symbols index src/                          # -> .ensemble/symbols.jsonl
ensemble graph symbols .ensemble/symbols.jsonl       # -> .ensemble/symbol-graph.jsonl
ensemble lsp symbols --flat src/ensemble/cli.py      # one-off documentSymbol query
ensemble lsp definition src/ensemble/cli.py 20 4     # zero-based line/character
```

Both indexing commands take `--out` to change the output path. `.ensemble/` is
gitignored. Paths are not limited to `ENSEMBLE_WORKSPACE`.

`SymbolLookup` and `ImpactAnalysis` (`ensemble.review`) are Python APIs only;
there is no CLI for them yet.

The LSP client starts a server per file type and needs it on `PATH`:

| Extensions | Server command |
|---|---|
| `.py` | `pyright-langserver --stdio` |
| `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | `typescript-language-server --stdio` |
| `.rs` | `rust-analyzer` |
| `.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.cxx` | `clangd --background-index` |
| `.cs` | `OmniSharp --languageserver` |
