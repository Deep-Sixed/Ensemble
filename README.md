# Local-First

Local-First is a local AI dev stack for JARVIS: model, repo context, code
intelligence, memory, tools, and UI stay local by default.

It runs a GGUF model through an OpenAI-compatible llama.cpp server, connects
through LangChain, and safely reads or proposes changes against selected local
repositories.

This is its own project. It is not a fork of Talent-Beacon or OpenMono. It
borrows Talent-Beacon's working conventions: Python project layout, Docker
discipline, `.env.example`, MCP access boundaries, and operator-controlled
behavior.

## Stack V1

Goal: run an AI coding/workflow environment where the model, repo context, code
intelligence, memory, tools, and UI stay local by default.

```text
VS Code / Cursor / TUI / CLI
        |
        v
Local AI Client / Agent Runner
        |
        +--> Default inference: llama.cpp OpenAI-compatible server
        |
        +--> MCP tools
        |       +--> filesystem MCP
        |       +--> Python MCP
        |       +--> code intelligence MCP
        |       +--> skills / markdown instructions
        |
        +--> Code intelligence layer
        |       +--> code indexing
        |       +--> Language Server Protocol
        |       +--> graph/context memory
        |
        +--> Docker sandbox
                +--> isolated execution
                +--> isolated dependencies
                +--> private local volumes
```

## Core Architecture

```text
Talent-Beacon = real app / workflow
Local-First   = local model + tool-control lab mounted against a workspace
```

Runtime shape:

```text
local-first CLI
  -> LangChain ChatOpenAI wrapper
  -> http://localhost:8080/v1
  -> llama-cpp-python server in Docker
  -> /models/qwen3.6-35b-a3b-ud-q4_k_xl.gguf
```

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
pipx install code-review-graph
code-review-graph --help
```

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

  src/local_first/
    config.py
    model.py
    mcp_registry.py
    sandbox_runner.py
    memory.py
    cli.py
```
