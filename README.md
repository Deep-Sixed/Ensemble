# Ensemble

Ensemble is a **repository intelligence / code context engine** for AI-assisted
development.

Its primary job is upstream preparation: discover relevant workspace content,
collect Git state, rank and prune context, attach task-relevant instructions,
and emit a bounded structured packet for downstream agents, routers, or model
gateways.

It does not host models, route providers, manage autonomous agent loops, own
durable project memory, or act as a provenance ledger.

## Primary API

```bash
ensemble context "Fix authentication timeout handling"
```

The command emits JSON with a stable top-level contract:

```json
{
  "schema_version": 1,
  "task": "Fix authentication timeout handling",
  "workspace": "/path/to/repo",
  "files": [],
  "symbols": [],
  "definitions": [],
  "references": [],
  "git_changes": {},
  "instructions": [],
  "context": "...",
  "token_estimate": 0,
  "token_budget": 12000,
  "truncated": false
}
```

PRs that deepen semantic intelligence populate the symbol/definition/reference
fields without changing the role of Ensemble.

## Responsibility boundary

```text
Workspace / IDE / Git / LSP
           |
           v
       Ensemble
  repository intelligence
           |
     rank / prune / annotate
           |
           v
 structured context packet
           |
           v
 downstream agent/router/model gateway
```

### Ensemble owns

- workspace discovery
- Git change context
- LSP queries
- symbol indexing
- disposable code graphs
- relevance ranking
- token-budgeted context assembly
- task-relevant skill/instruction injection
- VS Code integration

### Ensemble does not own

- llama.cpp/model lifecycle
- model or provider routing
- autonomous agent loops
- MCP server orchestration
- durable project memory
- provenance/event ledgers

The local symbol graph answers **"what code matters for this request?"** and is
disposable. Durable project knowledge belongs elsewhere.

### Workspace boundary

Every read stays under `ENSEMBLE_WORKSPACE`. Language servers are started with
a root no higher than the workspace, even inside a larger Git repository, and
definition/reference locations outside the workspace are counted in
`external_locations` rather than emitted as paths.

### Relevance

Files are ranked by task terms in their path, identifier matches in their
content (camelCase/snake_case aware), and uncommitted Git changes, before LSP
enrichment adds symbols, definitions and references.

## Configuration

```bash
export ENSEMBLE_WORKSPACE=/path/to/project
export ENSEMBLE_CONTEXT_TOKEN_BUDGET=12000
export ENSEMBLE_MAX_FILE_BYTES=200000
```

Settings can also live in a `.env` file (current directory first, then the
Ensemble checkout); values already exported in the shell win.

## Other CLI commands

```bash
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

Ensemble does not call models. Pipe the packet to whichever agent or client
does inference (Pi, Claude Code, Codex, Cursor, ...).

## Development

```bash
python3.14 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
```
