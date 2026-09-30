# Ensemble

Ensemble is a lean local AI development substrate for JARVIS: inference,
privacy, code context, MCP tools, and markdown-based operating guidance stay
local by default.

It runs a GGUF model through an OpenAI-compatible llama.cpp server, connects
through simple inspection utilities, and exposes local context to external
agent/coding tools.

Ensemble uses Qwen GGUF models through llama.cpp. On the current RTX 3060 Ti
machine, the multi-model router defaults to `qwen2.5-coder-7b-instruct-q4_k_m`
and the single-model stack defaults to `qwen3-4b-instruct-2507-ud-q4_k_xl` for
low-latency tool use. The larger `qwen3.6-35b-a3b-ud-q4_k_xl` model remains
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
        |     +-- Qwen2.5 Coder 7B router default (auto profile)
        |     +-- Qwen3 4B single-model default profile
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

Ensemble has two local serving stacks, each with its own default model:

| Stack | Compose file | Endpoint | Default model |
|---|---|---|---|
| Single-model | `docker-compose.yml` | `http://127.0.0.1:8888/v1` | `qwen3-4b-instruct-2507-ud-q4_k_xl` |
| Multi-model | `docker-compose.models.yml` | `http://127.0.0.1:8090/v1` (router) | `qwen2.5-coder-7b-instruct-q4_k_m` |

Inference lanes:

- Coding: llama.cpp plus Qwen2.5 Coder 7B Instruct GGUF. Router default, and
  the target of the `auto` and `coding` profiles.
- Fast/general: llama.cpp plus Qwen3 4B Instruct GGUF. Single-model default.
- Reasoning/offload: llama.cpp plus Qwen3.6 35B-A3B GGUF. Explicit selection
  only.
- Smoke: a tiny/small GGUF only for boot tests and endpoint wiring.

The smoke model proves Docker, llama.cpp, LangChain, MCP, CLI health, and
endpoint plumbing. The 35B model is useful for harder reasoning, but it is
larger than the card's VRAM and should be run deliberately with constrained
context and CPU/offload settings.

Profiles live under `profiles/`:

```bash
.venv/bin/ensemble profiles
```

Current profiles:

| Profile | Endpoint | Model | Use |
|---|---|---|---|
| `auto` | router `:8090` | `qwen2.5-coder-7b-instruct-q4_k_m` | `ENSEMBLE_PROFILE` default |
| `coding` | router `:8090` | `qwen2.5-coder-7b-instruct-q4_k_m` | Same as `auto` |
| `qwen3-4b` | `:8888` | `qwen3-4b-instruct-2507-ud-q4_k_xl` | Single-model 4B lane |
| `qwen3-4b-local` | `:8888` | `qwen3-4b-instruct-2507-ud-q4_k_xl` | Same as `qwen3-4b` |
| `reasoning` | `:8888` | `qwen3.6-35b-a3b-ud-q4_k_xl` | Single-model 35B lane |
| `qwen3.6-35b-a3b.local` | `:8888` | `qwen3.6-35b-a3b-ud-q4_k_xl.gguf` | Host-level `llama-server` (below) |
| `qwen3.6-35b-a3b.docker` | `:8080` | `qwen3.6-35b-a3b-ud-q4_k_xl` | Legacy port; no bundled stack listens on `:8080` |
| `qwen3.6-35b-a3b.lan` | `10.0.0.151:7474` | `qwen3.6-35b-a3b-ud-q4_k_xl` | LAN `llama-server` |
| `smoke.local` | `:8888` | `smoke-test` | Plumbing checks |

Profile precedence: `ENSEMBLE_PROFILE` only fills settings the environment
leaves unset. `ENSEMBLE_LLM_BASE_URL`, `ENSEMBLE_LLM_MODEL`, `ENSEMBLE_API_KEY`,
`ENSEMBLE_MAX_TOKENS`, and `ENSEMBLE_TEMPERATURE` win over it, and
`.env.example` sets all five for the single-model 4B server. With a fresh
`.env`, commands without `--profile` therefore talk to `:8888` even though
`ENSEMBLE_PROFILE=auto`.

`--profile` (on `health`, `models`, `ask`, and `chat`) uses that profile's
endpoint, model, token settings, and `api_key_env` key, and ignores those
five variables. It is the equivalent of picking another model from a model
selector:

```bash
.venv/bin/ensemble ask --profile auto "Summarize this repo."
.venv/bin/ensemble ask --profile reasoning "Reason through this design."
```

### Single-model stack

Default 4B lane:

```bash
docker compose --env-file docker/qwen3-4b.conf up -d llm
.venv/bin/ensemble health --profile qwen3-4b
```

Explicit 35B reasoning/offload lane:

```bash
docker compose --env-file docker/qwen3.6-35b.conf up -d llm
.venv/bin/ensemble health --profile reasoning
```

`docker/switch-qwen-model.sh` is a Compose-free alternative. It replaces a
standalone `ensemble-qwen` container on `:8888` (llama.cpp `server-vulkan`
image with the bundled web UI in `docker/llama-webui/`) and waits for
`/v1/models`. Stop the Compose `llm` service first; both bind `:8888`.

```bash
./docker/switch-qwen-model.sh qwen3-4b    # or: reasoning
```

### Multi-model stack

`docker-compose.models.yml` runs one llama.cpp server per model behind a
FastAPI router on `127.0.0.1:8090`. Each model service is a Compose profile,
so name the models you want. `up -d` without `--profile` starts only the
router, which then has no upstream to forward to.

```bash
docker compose -f docker-compose.models.yml --profile qwen25-coder --profile qwen3-4b up -d
curl -fsS http://127.0.0.1:8090/health
.venv/bin/ensemble ask --profile auto "Say hello from Ensemble."
```

| Compose profile | Router model ID | GGUF file in `models/` |
|---|---|---|
| `qwen25-coder` | `qwen2.5-coder` (default) | `qwen2.5-coder-7b-instruct-q4_k_m.gguf` |
| `qwen3-4b` | `qwen3-4b` | `qwen3-4b-instruct-2507-ud-q4_k_xl.gguf` |
| `qwen36-35b` | `qwen3.6-35b` | `qwen3.6-35b-a3b-ud-q4_k_xl.gguf` |
| `qwen35-uncensored` | `qwen3.5-uncensored` | `Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` |

The router also accepts the full GGUF names (for example
`qwen2.5-coder-7b-instruct-q4_k_m`) and sends unknown or missing model IDs to
the default. Its `/v1/models` list is static, so `ensemble health --profile
auto` reports OK even when no model service is running. Use `GET /health` to
see which upstreams respond.

`systemd/ensemble-models.service` runs the same `up -d` without profiles, so
it also starts only the router. To start models at boot, add a drop-in:

```ini
# sudo systemctl edit ensemble-models.service
[Service]
Environment=COMPOSE_PROFILES=qwen25-coder,qwen3-4b
```

### Other endpoints

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

.venv/bin/ensemble health --profile qwen3.6-35b-a3b.local
```

Hardware caveat: Qwen3.6-35B-A3B is the reasoning lane, but it should be run
deliberately on an RTX 3060 Ti. Keep context controlled, use llama.cpp
MoE/offload settings, and prefer the 4B or Coder 7B lanes for
coding/tool-heavy loops.

## Support Mechanics

Ensemble keeps support primitives for external coding tools. Each item is
marked with its current status; "planned" items have no code yet.

- Write/Edit separation (library only): `ensemble.tool_modes.plan_write`
  refuses to overwrite existing files, and `plan_edit` requires an existing
  file with a checkpoint. Not exposed through the CLI.
- Thinking budget (planned): keep local-model reasoning bounded and force
  implementation.
- Dynamic skill injection (implemented): `ensemble ask` prepends matching
  skill cards; `ensemble skills` previews them.
- Workspace discovery (planned): read local README/docs/instructions before
  editing.
- Malformed output repair (detection only): `ensemble.quality.needs_repair`
  flags empty replies and unparsed tool calls; nothing repairs them yet.
- Quality monitor (implemented): `ensemble ask` appends a quality-monitor note
  for empty replies and unparsed tool calls. Repeated-loop detection exists in
  `ensemble.quality.inspect_response`, but `ask` does not feed it a tool
  sequence.
- Checkpointing (implemented): `ensemble checkpoint <path>` copies a workspace
  file into `state/checkpoints/`.
- Retry with failing tests (planned): second attempt sees the failure output.

Useful local checks (checkpoint paths are relative to `ENSEMBLE_WORKSPACE`):

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
- Test `CodeGraphContext` second, in its own container or pipx environment if
  its Python compatibility lags behind this project's Python 3.14 baseline.
- Keep code intelligence as MCP-side capability, not baked into the core agent.

Built in: `ensemble lsp`, `ensemble symbols index`, and `ensemble graph symbols`
build LSP-backed symbol artifacts under `.ensemble/`. See
`docs/repo-intelligence.md`.

## Code Intelligence: code-review-graph

Ensemble can use `code-review-graph` as a developer-side code intelligence
MCP sidecar. It builds a local structural graph of the repo under
`.code-review-graph/` and exposes that graph to AI coding tools through MCP.

Install it outside the Ensemble app venv:

```bash
python3.14 -m pip install --user pipx
python3.14 -m pipx ensurepath
source ~/.bashrc
pipx install --python python3.14 code-review-graph
code-review-graph --help
```

pipx keeps `code-review-graph` and its native dependencies out of the Ensemble
`.venv`.

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

- Workspace reads (`files`, `read`, `checkpoint`, `ask --file`) are limited to
  `ENSEMBLE_WORKSPACE`. The code-intelligence commands (`lsp`,
  `symbols index`, `graph symbols`) read the paths they are given and are not
  workspace-guarded.
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

`make bootstrap` creates `.venv` with Python 3.14, installs `ensemble[dev]` in
editable mode, and runs the unit tests.

Run `ensemble` from the repository root. `profiles/`, `mcp/`, `skills/`, and
`state/checkpoints/` are resolved relative to the current directory. From
anywhere else, `ensemble profiles` prints nothing and every command fails with
`Profile not found` while `ENSEMBLE_PROFILE` is set.

The model is canonical at:

```text
/home/jarvis/projects/third-party/ensemble/models/qwen3-4b-instruct-2507-ud-q4_k_xl.gguf
/home/jarvis/projects/third-party/ensemble/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf
```

The multi-model stack also expects `qwen2.5-coder-7b-instruct-q4_k_m.gguf` and
`Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf` in `models/` for the
Compose profiles that use them.

Docker mounts `models/` read-only at `/models`. Choose the active model with
`ENSEMBLE_MODEL_PATH` and `ENSEMBLE_MODEL_ALIAS`, or use one of the `.conf`
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

For the 35B lane (`docker/qwen3.6-35b.conf`), use:

```json
"model": "qwen3.6-35b-a3b-ud-q4_k_xl"
```

Stop the server:

```bash
docker compose down
```

## Milestone 2: Python Client

`make bootstrap` (see Setup) installs the CLI into `.venv`. The manual
equivalent, with Python 3.14:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
source .venv/bin/activate
```

Check the endpoint:

```bash
ensemble health
ensemble health --profile qwen3-4b
ensemble health --profile reasoning
ensemble health --profile qwen3.6-35b-a3b.local
ensemble health --profile smoke.local
ensemble models
```

With `--profile`, `health`, `models`, `ask`, and `chat` use that JSON profile's
`base_url`, model, and `api_key_env` (so `.env` `ENSEMBLE_LLM_BASE_URL` does not
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
  tools/              # Code-intelligence sidecar notes
  systemd/
  models/             # GGUF weights (gitignored)
  state/              # Runtime checkpoints and evidence
```
