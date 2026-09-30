# Ensemble Agent Instructions

Ensemble is a **code context engine / repository intelligence layer**.

Its job is upstream context preparation for coding agents and AI clients:
workspace discovery, LSP queries, symbol indexing, disposable code graphs,
relevance ranking, context pruning, token budgeting, and structured hand-off.

Ensemble does **not** own model hosting, model/provider routing, autonomous agent
loops, MCP server orchestration, durable memory, or provenance ledgers.

## Repository layout

```text
src/ensemble/          Python context engine
ensemble-vscode/       VS Code / Cursor integration
skills/                task-relevant guidance
tests/                 pytest tests
docs/                  architecture notes
```

## Runtime

- Python 3.14.x (`>=3.14,<3.15`)
- Node 26.3.0 for the VS Code extension

## Boundaries

- Keep workspace reads scoped to `ENSEMBLE_WORKSPACE`.
- Treat symbol indexes and code graphs as disposable derived data.
- Do not add model lifecycle, routing, or agent orchestration back into Ensemble.
- Persistent project knowledge belongs outside Ensemble.
- Prefer structured context output over conversational UI.

## Development

```bash
make bootstrap
make test
```

Extension:

```bash
cd ensemble-vscode
npm install
npm run compile
npm run check
```

## Coding discipline

1. Keep diffs surgical.
2. Preserve the context-engine boundary.
3. Add tests for new context assembly/ranking behavior.
4. Avoid dependencies that duplicate downstream systems.
