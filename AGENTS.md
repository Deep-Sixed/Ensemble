# Ensemble Agent Instructions

Ensemble is a local AI development substrate. It follows these engineering standards: Python 3.14.5, Node 26.3.0 for the VS Code extension, KeePassXC-only secrets, surgical diffs, and operator-controlled mutations.

## Repository layout

```text
ensemble/
├── src/ensemble/          # Python package (CLI, config, skills, indexing)
├── ensemble-vscode/       # VS Code / Cursor extension (TypeScript + Biome)
├── router/                # FastAPI multi-model router
├── docker/                # Dockerfiles and model env files
├── profiles/              # JSON model endpoint profiles
├── mcp/                   # MCP server wiring (no secrets)
├── skills/                # Markdown operating guidance
├── scripts/               # Bootstrap and code-graph helpers
├── tests/                 # pytest unit tests
└── docs/                  # Architecture notes
```

## Runtime policy

| Runtime | Approved target |
|---------|-----------------|
| Python | **3.14.5** (`requires-python = ">=3.14,<3.15"`) |
| Docker Python base | `python:3.14.5-slim-trixie` |
| Node (extension) | **26.3.0** exact |

## Path conventions

| Variable | Default |
|----------|---------|
| `ENSEMBLE_ROOT` | Repo checkout (inferred by `ensemble.paths.repo_root()`), else current directory |
| `ENSEMBLE_HOST_MODEL_DIR` | `$ENSEMBLE_ROOT/models` |
| `ENSEMBLE_WORKSPACE` | Current directory; set in `.env` to the project Ensemble reads, outside this repo |

Never hardcode absolute host paths. Use env vars or `ensemble.paths.repo_root()`.

## Inference stacks

Two supported local stacks:

1. **Single-model** (`docker-compose.yml`) — llama-cpp-python on port **8888**, default Qwen3 4B.
2. **Multi-model** (`docker-compose.models.yml`) — per-model llama.cpp servers + router on port **8090**.

Profiles in `profiles/` select endpoints. Default profile `auto` targets the router at `http://127.0.0.1:8090/v1`.

## Secrets

- **KeePassXC only** — never commit `.env`, tokens, or API keys.
- MCP configs are wiring only; load secrets at runtime via the operator shell.
- Do not embed credentials in git remotes.

## Development workflow

```bash
make bootstrap    # .venv + editable install + pytest smoke
make test         # pytest unit tests
```

Extension build (requires Node **26.3.0** — see `.nvmrc`):

```bash
cd ensemble-vscode
# nvm use   # or fnm use, if available
npm install
npm run compile
npm run check     # Biome lint + format
```

## Safety boundaries

- `ENSEMBLE_ALLOW_WRITES=false` and `ENSEMBLE_ALLOW_SHELL=false` by default.
- No auto-submit, auto-send, or mailbox mutation from Ensemble.
- Workspace filesystem access stays scoped to `ENSEMBLE_WORKSPACE` unless operator approves broader access.

## Coding discipline

1. Surgical changes — touch only what the task requires.
2. Match existing conventions in `src/ensemble/`.
3. Report exact test commands and results.
4. Do not add dependencies without justification.

## Task report footer

```text
AI Brain: <executor name>
Model/Tool: <model or tool name>
Role: <implementation | review | reconciliation | audit>
```
