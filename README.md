# Ensemble

Ensemble is a lean local AI development substrate for JARVIS: inference,
privacy, code context, MCP tools, and markdown-based operating guidance stay
local by default.

It runs a GGUF model through an OpenAI-compatible llama.cpp server, connects
through simple inspection utilities, and exposes local context to external
agent/coding tools.

Ensemble uses Qwen GGUF models through llama.cpp. On the current RTX 3060 Ti
machine, the default lane is `qwen3-4b-instruct-2507-ud-q4_k_xl` for daily coding
and low-latency tool use. The larger `qwen3.6-35b-a3b-ud-q4_k_xl` model remains
available as an explicit reasoning/offload lane, but it should not be the
default on this VRAM budget.

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
- simple CLI commands: `ensemble health`, `ensemble mcp`,
  `ensemble profiles`

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
        |     +-- Qwen3 4B coding default profile
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
Nexus = real app / workflow
Ensemble      = local model + tool-control lab mounted against a workspace
```

Runtime shape:

```text
external agent/coding tool
  -> Ensemble endpoint/profile/MCP config
  -> llama.cpp OpenAI-compatible server
  -> local GGUF model and local repo context
```

## Model Strategy

Ensemble has three inference lanes:

- Coding/default inference: llama.cpp plus Qwen3 4B Instruct GGUF.
- Reasoning/offload inference: llama.cpp plus Qwen3.6 35B-A3B GGUF.
- Smoke inference: a tiny/small GGUF only for boot tests and endpoint wiring.

The smoke model proves Docker, llama.cpp, LangChain, MCP, CLI health, and
endpoint plumbing. The 4B model is the default daily driver for an RTX 3060 Ti.
The 35B model is useful for harder reasoning, but it is larger than the card's
VRAM and should be run deliberately with constrained context and CPU/offload
settings.

Profiles live under `profiles/`:

```bash
.venv/bin/ensemble profiles
```

Current profiles:

```text
auto.json                         # default: qwen3-4b coding lane
qwen3-4b-local.json
qwen3.6-35b-a3b.docker.json
qwen3.6-35b-a3b.lan.json
qwen3.6-35b-a3b.local.json
smoke.local.json
```

Model selection policy:

```text
Auto / default  -> qwen3-4b-instruct-2507-ud-q4_k_xl
Reasoning 35B   -> qwen3.6-35b-a3b-ud-q4_k_xl
Smoke           -> smoke-test
```

Leave `ENSEMBLE_PROFILE=auto` for default behavior. Use `--profile` when you
want the equivalent of picking another model from a model selector:

```bash
.venv/bin/ensemble ask --profile auto "Summarize this repo."
.venv/bin/ensemble ask --profile qwen3.6-35b-a3b.local "Reason through this design."
```

Default Docker lane:

```bash
docker compose --env-file docker/qwen3-4b.conf up -d llm
.venv/bin/ensemble health --profile auto
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
  --port 8888 \
  --jinja \
  -c 16384 \
  -ngl 99 \
  --n-cpu-moe 999 \
  --flash-attn on
```

Hardware caveat: Qwen3.6-35B-A3B is the reasoning lane, but it should be run
deliberately on an RTX 3060 Ti. Keep context controlled, use llama.cpp
MoE/offload settings, and prefer the 4B profile for coding/tool-heavy loops.

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
| Memory | Thread/project memory | Stores reusable project facts, decisions, and architecture notes |
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
- Test `CodeGraphContext` second, likely in a Python 3.14 container if its
  Python compatibility lags behind this project's Python 3.15 baseline.
- Keep code intelligence as MCP-side capability, not baked into the core agent.

## Code Intelligence: code-review-graph

Ensemble can use `code-review-graph` as a developer-side code intelligence
MCP sidecar. It builds a local structural graph of the repo under
`.code-review-graph/` and exposes that graph to AI coding tools through MCP.

Install it outside the Ensemble app venv:

```bash
python3.15 -m pip install --user pipx
python3.15 -m pipx ensurepath
source ~/.bashrc
pipx install --python /usr/bin/python3.14 code-review-graph
code-review-graph --help
```

`code-review-graph` is installed with Python 3.14 because one transitive native
dependency currently fails to build under Python 3.15.

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

- Reads are limited to `ENSEMBLE_WORKSPACE`.
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
    "model": "qwen3.6-35b-a3b-ud-q4_k_xl",
    "messages": [{"role": "user", "content": "Say hello from Ensemble."}],
    "temperature": 0.2
  }'
```

For the default 4B lane, use:

```json
"model": "qwen3-4b-instruct-2507-ud-q4_k_xl"
```

Stop the server:

```bash
docker compose down
```

### Multi-model stack

Each backend in `docker-compose.models.yml` is opt-in via a Compose profile;
the router (port 8090) starts without any. Select the backends to run:

```bash
docker compose -f docker-compose.models.yml --profile qwen25-coder --profile qwen3-4b up -d
docker compose -f docker-compose.models.yml --profile "*" down
```

`systemd/ensemble-models.service` starts `qwen25-coder` and `qwen3-4b`; edit its
`--profile` flags to change that.

## Milestone 2: Python Client

Install the CLI in a Python 3.15 environment:

```bash
python -m pip install -e .
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

With `--profile`, `health` and `models` use that JSON profile’s `base_url` and
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

By default, the workspace is:

```text
/home/jarvis/projects/nexus
```

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
  models/             # GGUF weights (gitignored)
  state/              # Runtime checkpoints and evidence
```
