# Local-First

Local-First is a lean local AI development substrate for JARVIS: inference,
privacy, code context, MCP tools, and markdown-based operating guidance stay
local by default.

It runs a GGUF model through an OpenAI-compatible llama.cpp server, connects
through simple inspection utilities, and exposes local context to external
agent/coding tools.

Local-First is optimized around Qwen3.6-35B-A3B through llama.cpp. Smaller
models may be used for smoke tests, but they are not the target experience. The
core bet is scaffold-model fit: local coding models perform much better when the
harness is designed around their strengths and weaknesses.

The substrate is load-bearing. Local-First is not positioned as "run a local
model through a generic agent loop"; it is positioned as a local launchpad for
Qwen-class coding workflows.

This is its own project. It is not a fork of Talent-Beacon or OpenMono. It
borrows Talent-Beacon's working conventions: Python project layout, Docker
discipline, `.env.example`, MCP access boundaries, and operator-controlled
behavior.

## Purpose

A lean local AI dev substrate for inference, privacy, code context, MCP tools,
and markdown-based operating guidance.

Local-First should provide:

- model profiles
- llama.cpp server wiring
- Docker sandbox/runtime
- MCP configuration
- code-index sidecar configs
- markdown skills
- simple CLI commands: `local-first health`, `local-first mcp`,
  `local-first profiles`

Local-First should avoid:

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
Local-First Substrate
        |
        +-- Inference
        |     +-- llama.cpp OpenAI-compatible endpoint
        |     +-- Qwen3.6-35B-A3B target profile
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
Talent-Beacon = real app / workflow
Local-First   = local model + tool-control lab mounted against a workspace
```

Runtime shape:

```text
external agent/coding tool
  -> Local-First endpoint/profile/MCP config
  -> llama.cpp OpenAI-compatible server
  -> local GGUF model and local repo context
```

## Model Strategy

Local-First has two inference lanes:

- Target inference: llama.cpp plus Qwen3.6-35B-A3B GGUF.
- Smoke inference: a tiny/small GGUF only for boot tests and endpoint wiring.

The smoke model proves Docker, llama.cpp, LangChain, MCP, CLI health, and
endpoint plumbing. The target model proves the Local-First coding-agent thesis.

Profiles live under `profiles/`:

```bash
.venv/bin/local-first profiles
```

Current profiles:

```text
qwen3.6-35b-a3b.lan.json
qwen3.6-35b-a3b.local.json
smoke.local.json
```

Use the LAN profile when the existing Docker `llama-server` is bound to
`10.0.0.151:7474`:

```bash
.venv/bin/local-first health --profile qwen3.6-35b-a3b.lan
curl -fsS http://10.0.0.151:7474/v1/models
```

Target Qwen server shape, when running a host-level `llama-server`:

```bash
export LLAMACPP_API_KEY=noop

llama-server \
  -m /home/jarvis/openmono.ai/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf \
  --host 127.0.0.1 \
  --port 8888 \
  --jinja \
  -c 16384 \
  -ngl 99 \
  --n-cpu-moe 999 \
  --flash-attn on
```

Hardware caveat: Qwen3.6-35B-A3B is the target, but it should be run
deliberately. Keep context controlled, use llama.cpp MoE/offload settings, and
use smoke profiles only to debug plumbing.

## Support Mechanics

Local-First keeps support primitives for external coding tools:

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
.venv/bin/local-first skills "prepare a patch for the model abstraction"
.venv/bin/local-first checkpoint README.md
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

Local-First is the launchpad, not the airplane.

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

Local-First can use `code-review-graph` as a developer-side code intelligence
MCP sidecar. It builds a local structural graph of the repo under
`.code-review-graph/` and exposes that graph to AI coding tools through MCP.

Install it outside the Local-First app venv:

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
      "cwd": "/home/jarvis/local-first"
    }
  }
}
```

The graph is local-only and should not be committed.

First test prompt after setup:

```text
Use code-review-graph to inspect this Local-First repo. Give me:
1. the main entry points,
2. the most connected files,
3. the current architecture map,
4. what files would be affected if I changed the model abstraction layer.
```

## Safety Defaults

v1 is deliberately conservative:

- Reads are limited to `LOCAL_FIRST_WORKSPACE`.
- Writes are disabled by default.
- Shell execution is disabled by default.
- The Docker model mount is read-only.
- Patch proposal mode should come before automatic writes.

## Setup

Create local config:

```bash
cd /home/jarvis/local-first
cp .env.example .env
```

The model is canonical at:

```text
/home/jarvis/openmono.ai/models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf
```

`models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf` is a symlink marker only. Docker mounts
the canonical model directory directly so the container can resolve the file.

## Milestone 1: Model Server

Build and start the server:

```bash
docker compose up -d llm
```

Confirm the OpenAI-compatible models endpoint:

```bash
curl -fsS http://localhost:8080/v1/models
```

Confirm a chat completion:

```bash
curl -fsS http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer local-first" \
  -d '{
    "model": "qwen3.6-35b-a3b-ud-q4_k_xl",
    "messages": [{"role": "user", "content": "Say hello from Local-First."}],
    "temperature": 0.2
  }'
```

Stop the server:

```bash
docker compose down
```

## Milestone 2: Python Client

Install the CLI in a Python 3.15 environment:

```bash
python -m pip install -e .
```

Check the endpoint:

```bash
local-first health
local-first models
```

Ask one question:

```bash
local-first ask "What are you?"
```

Start a simple loop:

```bash
local-first chat --classic
```

## Milestone 3: Read-Only Repo Context

By default, the workspace is:

```text
/home/jarvis/jarvis/talent-beacon
```

List files:

```bash
local-first files . --limit 50
```

Read one file:

```bash
local-first read README.md
```

Ask with file context:

```bash
local-first ask "Summarize this file in five bullets." --file README.md
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
/home/jarvis/local-first
  docker-compose.yml
  .env.example
  README.md

  docker/
    llama-cpp-python.Dockerfile
    agent.Dockerfile

  models/
    qwen3.6-35b-a3b-ud-q4_k_xl.gguf -> /home/jarvis/openmono.ai/models/...

  profiles/
    qwen3.6-35b-a3b.local.json
    smoke.local.json

  mcp/
    filesystem.json
    code-review-graph.json
    codebase-memory.json
    python-tools.json

  skills/
    local-first.md
    repo-audit.md
    safe-coding.md
    docker-sandbox.md
    tools/
      guarded-tools.md
    protocols/
      small-model-native-agent.md
      patch-proposal.md

  state/
    checkpoints/
    evidence/

  src/local_first/
    checkpoints.py
    config.py
    memory.py
    model.py
    mcp_registry.py
    quality.py
    sandbox_runner.py
    skills.py
    tool_modes.py
    cli.py
```
