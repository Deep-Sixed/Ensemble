# Ensemble

Ensemble is the developer-facing client layer for the local AI stack.

It owns editor and CLI ergonomics, local code context, LSP queries, disposable
symbol indexes, skill cards, and lightweight pre-edit checkpoints. It does not
host models, choose inference runtimes, route providers, own long-running agent
execution, or maintain a durable knowledge graph.

## Responsibility boundary

```text
VS Code / CLI
      |
      v
   Ensemble
      |
      +-- LSP / symbols / skills / local context
      |
      v
downstream OpenAI-compatible endpoint
```

In the broader stack, model/runtime fulfillment belongs downstream (for example
InferenceDeck), routing/policy belongs to the routing layer (for example
Cerberus), durable agent execution belongs to an agent runtime, and persistent
context/provenance belongs to their dedicated systems.

## What stays in Ensemble

- VS Code extension
- thin CLI and HTTP client
- LSP queries: hover, definition, references, document symbols
- disposable symbol index and lightweight symbol graph
- local review/impact lookup
- task-relevant skill cards
- read-only workspace inspection
- lightweight pre-edit checkpoints

## What Ensemble intentionally does not own

- llama.cpp or model-process lifecycle
- Docker/systemd model hosting
- model fallback or provider routing
- MCP server registry
- durable agent scheduling or subagents
- persistent memory/knowledge graphs
- provenance/event ledgers
- general-purpose sandbox orchestration

## Configuration

```bash
export ENSEMBLE_BASE_URL=http://127.0.0.1:8090/v1
export ENSEMBLE_MODEL=auto
export ENSEMBLE_API_KEY=ensemble
export ENSEMBLE_WORKSPACE=/path/to/project
```

Optional:

```bash
export ENSEMBLE_MAX_FILE_BYTES=200000
export ENSEMBLE_CHECKPOINT_DIR=.ensemble/checkpoints
```

## CLI

```bash
ensemble health
ensemble models
ensemble ask "Summarize this repository"
ensemble ask "Review this file" --file src/example.py
ensemble chat

ensemble files
ensemble read README.md
ensemble skills "review this patch"
ensemble checkpoint README.md

ensemble lsp hover src/example.py 10 4
ensemble lsp definition src/example.py 10 4
ensemble lsp references src/example.py 10 4
ensemble lsp symbols src/example.py

ensemble symbols src --out .ensemble/symbols.jsonl
ensemble graph .ensemble/symbols.jsonl --out .ensemble/symbol-graph.jsonl
```

The symbol graph is a disposable developer index, not a source of durable truth.

## Development

```bash
python3.14 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
```
