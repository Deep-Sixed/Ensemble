# Ensemble

Ensemble is a lean local AI development substrate for JARVIS: inference,
privacy, code context, MCP tools, and markdown-based operating guidance stay
local by default.

It runs a GGUF model through an OpenAI-compatible llama.cpp server, connects
through simple inspection utilities, and exposes local context to external
agent/coding tools.

Ensemble uses Qwen GGUF models through llama.cpp. On the current RTX 3060 Ti
machine, the default lane is `qwen2.5-coder-7b-instruct-q4_k_m` for daily coding,
served through the multi-model router on port 8090. `qwen3-4b-instruct-2507-ud-q4_k_xl`
is the fast/general lane (also the single-model Docker stack default on port 8888).
The larger `qwen3.6-35b-a3b-ud-q4_k_xl` model remains available as an explicit
reasoning/offload lane, but it should not be the default on this VRAM budget.

The substrate is load-bearing. Ensemble is not positioned as "run a local
model through a generic agent loop"; it is positioned as a local launchpad for
Qwen-class coding workflows.

This is its own project. It is not a fork of Nexus or OpenMono. It
borrows Nexus's working conventions: Python project layout, Docker
discipline, `.env.example`, MCP access boundaries, and operator-controlled
behavior.

## Purpose

A lean local AI dev substrate for inference, privacy, code context, MCP tools,
and markdown-based operating guidance.

Ensemble should provide:

- model profiles
- llama.cpp server wiring
- Docker sandbox/runtime
- MCP configuration
- code-index sidecar configs
- markdown skills
- simple CLI commands (`ensemble --help` lists them all):
  - endpoint inspection: `health`, `models`, `profiles`, `mcp`
  - read-only workspace access: `files`, `read`
  - model calls: `ask`, `chat`
  - support primitives: `skills`, `checkpoint`
  - code intelligence: `lsp`, `symbols index`, `graph symbols`

Ensemble should avoid:

- custom agent loop
- custom planner
- auto-edit system
- dashboard
- complex memory engine
- replacing Codex, Cursor, OpenCode, pi, or little-coder

## Stack V1

Goal: run an AI coding/workflow environment where the model, repo context, code
intelligence, memory, tools, and UI stay local by default.

```text
VS Code / Cursor / OpenCode / TUI / CLI
        |
        v
External Agent / Coding Tool
        |
        v
Ensemble Substrate
        |
        +-- Inference
        |     +-- llama.cpp OpenAI-compatible endpoint
        |     +-- Qwen2.5 Coder 7B coding default profile (router)
        |     +-- Qwen3 4B fast/general profile
        |     +-- Qwen3.6 35B explicit reasoning/offload profile
        |     +-- smoke profile for plumbing checks
        |
        +-- Privacy / Isolation
        |     +-- Docker Compose
        |     +-- local volumes
        |     +-- no cloud inference required
        |
        +-- MCP
        |     +-- filesystem MCP
        |     +-- optional Python MCP
        |     +-- code-review/code-index sidecars
        |
        +-- Code Intelligence
        |     +-- code indexing
        |     +-- Language Server Protocol
        |     +-- CodeGraphContext / codebase-memory-mcp style tools
        |
        +-- Extensibility
              +-- Skills as Markdown
              +-- project instructions
              +-- tool usage notes
              +-- protocol notes
```

## Core Architecture

```text
Nexus    = real app / workflow
Ensemble = local model + tool-control lab mounted against a workspace
```

Runtime shape:

```text
external agent/coding tool
  -> Ensemble endpoint/profile/MCP config
  -> llama.cpp OpenAI-compatible server
  -> local GGUF model and local repo context
```

## Model Strategy

Ensemble has four inference lanes:

- Coding/default inference: llama.cpp plus Qwen2.5 Coder 7B Instruct GGUF,
  reached through the router on port 8090.
- Fast/general inference: llama.cpp plus Qwen3 4B Instruct GGUF.
- Reasoning/offload inference: llama.cpp plus Qwen3.6 35B-A3B GGUF.
- Smoke inference: a tiny/small GGUF only for boot tests and endpoint wiring.

The smoke model proves Docker, llama.cpp, LangChain, MCP, CLI health, and
endpoint plumbing. The 7B coder is the default daily driver for an RTX 3060 Ti;
Qwen3 4B is the lighter option and the default of the single-model stack.
The 35B model is useful for harder reasoning, but it is larger than the card's
VRAM and should be run deliberately with constrained context and CPU/offload
settings.

There are two supported stacks (see `AGENTS.md`):

| Stack | Compose file | Endpoint | Default model |
|---|---|---|---|
| Multi-model | `docker-compose.models.yml` | router, `http://127.0.0.1:8090/v1` | `qwen2.5-coder` |
| Single-model | `docker-compose.yml` | llama-cpp-python, `http://127.0.0.1:8888/v1` | Qwen3 4B |

The router (`router/main.py`) proxies `/v1/chat/completions` to per-model
llama.cpp containers, serves `/v1/models`, and exposes `/health` with
per-upstream status. It maps full GGUF names to router IDs (for example
`qwen3-4b-instruct-2507-ud-q4_k_xl` -> `qwen3-4b`), and falls back to the
default model when the `model` field is missing or `default`. Start the
multi-model stack with:

```bash
docker compose -f docker-compose.models.yml --profile qwen25-coder up -d
.venv/bin/ensemble health --profile auto
```

Each model service sits behind a compose profile (`qwen25-coder`, `qwen3-4b`,
`qwen36-35b`, `qwen35-uncensored`); enable only the ones you need with
additional `--profile` flags. The router starts with any of them.

Profiles live under `profiles/`:

```bash
.venv/bin/ensemble profiles
```

Current profiles:

```text
auto.json                         # default: qwen2.5-coder 7B via router :8090
coding.json                       # qwen2.5-coder 7B via router :8090
qwen3-4b.json                     # qwen3-4b on :8888 (single-model stack)
qwen3-4b-local.json               # qwen3-4b on :8888
reasoning.json                    # qwen3.6-35b on :8888, 8192 context
qwen3.6-35b-a3b.docker.json       # qwen3.6-35b on :8888, 8192 context
qwen3.6-35b-a3b.local.json        # qwen3.6-35b host llama-server on :8080
qwen3.6-35b-a3b.lan.json          # qwen3.6-35b on 10.0.0.151:7474, 196608 context
smoke.local.json                  # smoke-test on :8888, 4096 context
```

Model selection policy:

```text
Auto / default  -> qwen2.5-coder-7b-instruct-q4_k_m
Fast / general  -> qwen3-4b-instruct-2507-ud-q4_k_xl
Reasoning 35B   -> qwen3.6-35b-a3b-ud-q4_k_xl
Smoke           -> smoke-test
```

Leave `ENSEMBLE_PROFILE=auto` for default behavior. Use `--profile` when you
want the equivalent of picking another model from a model selector:

```bash
.venv/bin/ensemble ask --profile auto "Summarize this repo."
.venv/bin/ensemble ask --profile qwen3.6-35b-a3b.local "Reason through this design."
```

Single-model Docker lane (Qwen3 4B on port 8888):

```bash
docker compose --env-file docker/qwen3-4b.conf up -d llm
.venv/bin/ensemble health --profile qwen3-4b
```

Explicit 35B reasoning/offload lane:

```bash
docker compose --env-file docker/qwen3.6-35b.conf up -d llm
.venv/bin/ensemble health --profile qwen3.6-35b-a3b.docker
```

Use the LAN profile when the existing Docker `llama-server` is bound to
`10.0.0.151:7474`:

```bash
.venv/bin/ensemble health --profile qwen3.6-35b-a3b.lan
curl -fsS http://10.0.0.151:7474/v1/models
```

Large Qwen server shape, when running a host-level `llama-server`:

```bash
export LLAMACPP_API_KEY=noop

llama-server \
  -m /home/jarvis/projects/third-party/ensemble/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  --jinja \
  -c 8192 \
  -ngl 99 \
  --n-cpu-moe 999 \
  --flash-attn on
```

That shape matches the `qwen3.6-35b-a3b.local` profile (port 8080, 8192
context). Raise `-c` only together with that profile's `context_window`.

Hardware caveat: Qwen3.6-35B-A3B is the reasoning lane, but it should be run
deliberately on an RTX 3060 Ti. Keep context controlled, use llama.cpp
MoE/offload settings, and prefer the 7B coder or 4B profile for
coding/tool-heavy loops.

## Support Mechanics

Ensemble keeps support primitives for external coding tools:

- Write/Edit separation: `Write` refuses to overwrite existing files; existing
  files must go through `Edit`.
- Thinking budget: keep local-model reasoning bounded and force implementation.
- Dynamic skill injection: inject compact tool/protocol cards only when needed.
- Workspace discovery: read local README/docs/instructions before editing.
- Malformed output repair: detect bad tool-call formatting and repair before
  restarting a turn.
- Quality monitor: catch empty replies, fake tools, and repeated loops.
- Checkpointing: snapshot files before any edit-capable flow.
- Retry with failing tests: second attempt sees the failure output.

Implementation status:

- Implemented as library primitives, not yet exposed as agent tools:
  Write/Edit separation (`src/ensemble/tool_modes.py`, `plan_write` and
  `plan_edit`), checkpoints (`checkpoints.py`), workspace/write/shell guards
  (`safety.py`), skill-card selection (`skills.py`), and quality checks
  (`quality.py`). `plan_edit` refuses to edit without a prior checkpoint.
- Detection only: `quality.py` flags empty replies, fake tools, and loops, and
  `needs_repair` spots bad tool-call output. Automatic repair and retry with
  failing tests are not implemented; they are planned in `docs/harness-roadmap.md`.

Useful local checks:

```bash
.venv/bin/ensemble skills "prepare a patch for the model abstraction"
.venv/bin/ensemble checkpoint README.md
```

The current implementation still defaults to substrate behavior: inspect
profiles, inspect MCP config, expose skills, and create checkpoints. Automatic
writes remain out of v1 scope.

See `docs/harness-roadmap.md` for the staged support-mechanics plan.

## Components

| Area | Choice | Purpose |
|---|---|---|
| Inference | llama.cpp server | Local model runtime, OpenAI-compatible API, no per-token API bill |
| Cost model | Context cost only | Main cost is hardware, electricity, and context-window limits |
| Privacy | Docker + local volumes | Keeps repo, memory, and logs isolated from cloud tools |
| Sandboxing | Docker | Lets tools run with a narrower blast radius |
| Code intelligence | Code indexing + LSP | Gives repo awareness without blindly reading files |
| Memory | Append-only `.ensemble/memory.md` per workspace | Minimal project notes (`memory.py`); durable cross-agent memory lives on the Nexus MCP bus, not in Ensemble |
| Extensibility | Skills in Markdown | Reusable instructions, workflows, checklists, and project habits |
| MCP | Filesystem/Python/code intelligence MCP | Controlled tool access |
| UI | VS Code, Cursor, TUI, CLI | Visual coding, terminal control, or automation |

Ensemble is the launchpad, not the airplane.

## Code Intelligence Layer

LSP provides editor-style intelligence: definitions, references, symbols,
diagnostics, imports, type hints, and rename awareness.

Code indexing provides AI-friendly repo memory: callers, route locations,
related modules, changed areas, dead-code signals, and architecture impact.

Default v1 direction:

- Test `codebase-memory-mcp` first because it is binary-based and local-only.
- Test `code-review-graph` as a developer-side MCP sidecar for structural code
  intelligence and blast-radius queries.
- Test `CodeGraphContext` second, likely in its own Python 3.14 container if
  its dependencies lag behind this project's Python 3.14.5 baseline.
- Keep code intelligence as MCP-side capability, not baked into the core agent.

## Code Intelligence: code-review-graph

Ensemble can use `code-review-graph` as a developer-side code intelligence
MCP sidecar. It builds a local structural graph of the repo under
`.code-review-graph/` and exposes that graph to AI coding tools through MCP.

Install it outside the Ensemble app venv, using Python 3.14:

```bash
python3.14 -m pip install --user pipx
python3.14 -m pipx ensurepath
source ~/.bashrc
pipx install --python /usr/bin/python3.14 code-review-graph
code-review-graph --help
```

It stays out of the app venv so its dependencies cannot affect Ensemble's
pinned runtime. See `mcp/code-review-graph.json` for the MCP wiring and
`tools/code-intelligence/README.md` for the sidecar policy.

Build the graph:

```bash
./scripts/build_code_graph.sh
```

Watch for changes while coding:

```bash
./scripts/watch_code_graph.sh
```

MCP config:

```json
{
  "mcpServers": {
    "code-review-graph": {
      "command": "code-review-graph",
      "args": ["serve"],
      "cwd": "/home/jarvis/projects/third-party/ensemble"
    }
  }
}
```

The graph is local-only and should not be committed.

## Code Intelligence: Symbol Index

Ensemble also builds its own small, durable symbol index from LSP output:

```bash
.venv/bin/ensemble symbols index src/ensemble
.venv/bin/ensemble graph symbols .ensemble/symbols.jsonl
```

These write `.ensemble/symbols.jsonl` and `.ensemble/symbol-graph.jsonl`, which
`SymbolLookup` and `ImpactAnalysis` (`src/ensemble/review/`) read. See
`docs/repo-intelligence.md`.

First test prompt after setup:

```text
Use code-review-graph to inspect this Ensemble repo. Give me:
1. the main entry points,
2. the most connected files,
3. the current architecture map,
4. what files would be affected if I changed the model abstraction layer.
```

## Safety Defaults

v1 is deliberately conservative:

- Reads are limited to `ENSEMBLE_WORKSPACE`. The default workspace is
  `/home/jarvis/projects/nexus`, a separate project Ensemble is mounted
  against, not this repo; set `ENSEMBLE_WORKSPACE` to point elsewhere.
- Writes are disabled by default.
- Shell execution is disabled by default.
- The Docker model mount is read-only.
- Patch proposal mode should come before automatic writes.

## Setup

Create local config:

```bash
cd /home/jarvis/projects/third-party/ensemble
cp .env.example .env
make bootstrap
```

The model is canonical at:

```text
/home/jarvis/projects/third-party/ensemble/models/qwen3-4b-instruct-2507-ud-q4_k_xl.gguf
/home/jarvis/projects/third-party/ensemble/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf
```

Docker mounts `models/` read-only at `/models`. Choose the active model with
`ENSEMBLE_MODEL_PATH` and `ENSEMBLE_MODEL_ALIAS`, or use one of the env
files under `docker/`.

## Milestone 1: Model Server

Build and start the server:

```bash
docker compose --env-file docker/qwen3-4b.conf up -d llm
```

Confirm the OpenAI-compatible models endpoint:

```bash
curl -fsS http://localhost:8888/v1/models
```

Confirm a chat completion:

```bash
curl -fsS http://localhost:8888/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ensemble" \
  -d '{
    "model": "qwen3-4b-instruct-2507-ud-q4_k_xl",
    "messages": [{"role": "user", "content": "Say hello from Ensemble."}],
    "temperature": 0.2
  }'
```

The `model` must match the alias of the loaded model. For the 35B lane
(`docker/qwen3.6-35b.conf`), use `"qwen3.6-35b-a3b-ud-q4_k_xl"`.

Stop the server:

```bash
docker compose down
```

## Milestone 2: Python Client

Install the CLI in a Python 3.14.5 environment (`make bootstrap` does this
and checks the patch version):

```bash
python3.14 -m pip install -e .
```

Check the endpoint:

```bash
ensemble health
ensemble health --profile qwen3-4b-local
ensemble health --profile qwen3.6-35b-a3b.docker
ensemble health --profile qwen3.6-35b-a3b.local
ensemble health --profile smoke.local
ensemble models
```

With `--profile`, `health` and `models` use that JSON profile's `base_url` and
`api_key_env` for the request (so `.env` `ENSEMBLE_LLM_BASE_URL` does not
override the profile when you are probing a specific server).

Ask one question:

```bash
ensemble ask "What are you?"
```

Start a simple loop:

```bash
ensemble chat --classic
```

## Milestone 3: Read-Only Repo Context

By default, the workspace is `ENSEMBLE_WORKSPACE`:

```text
/home/jarvis/projects/nexus
```

This is the project Ensemble is mounted against, not the Ensemble repo.

List files:

```bash
ensemble files . --limit 50
```

Read one file:

```bash
ensemble read README.md
```

Ask with file context:

```bash
ensemble ask "Summarize this file in five bullets." --file README.md
```

## Later Milestones

Milestone 4: patch proposal mode

- Generate unified diffs only.
- Human applies patches manually.
- No automatic writes.

Milestone 5: controlled write mode

- Allow writes only inside approved paths.
- Require dry-run preview.
- Keep an audit log.

Shell tools should stay out until the read-only and patch proposal flows are
boringly reliable.

## License

Released under the MIT License; see `LICENSE`. Agent and contributor
conventions live in `AGENTS.md`.

## Project Layout

```text
/home/jarvis/projects/third-party/ensemble/
  AGENTS.md
  Makefile
  docker-compose.yml
  docker-compose.models.yml
  .env.example
  README.md

  src/ensemble/       # Python package
  ensemble-vscode/    # VS Code / Cursor extension
  router/             # Multi-model FastAPI router
  docker/
  profiles/
  mcp/
  skills/
  scripts/
  tests/
  docs/
  systemd/
  tools/              # Code-intelligence sidecar notes
  models/             # GGUF weights (gitignored)
  state/              # Runtime checkpoints and evidence
```
