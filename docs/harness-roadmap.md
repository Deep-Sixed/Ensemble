# Substrate Support Roadmap

Ensemble is not a replacement agent framework. It is a local substrate that
supports external coding tools with model profiles, local inference, MCP config,
code intelligence sidecars, markdown skills, checkpoints, and evidence folders.

The thesis:

```text
Qwen3.6-35B-A3B becomes valuable when the surrounding substrate and external
tooling are designed for local-model behavior instead of frontier-model behavior.
```

## Milestones

### 1A: Model Profiles

Status: done.

- Coding profiles (`auto`, `coding`): Qwen2.5 Coder 7B through the llama.cpp
  router. Fast/general profile (`qwen3-4b`): Qwen3 4B.
- Reasoning profile (`reasoning`): Qwen3.6-35B-A3B through llama.cpp, explicit
  selection only.
- Smoke profile: tiny/small model for endpoint plumbing only.
- Profiles capture endpoint, context window, token budget, temperature, and
  zero-cost accounting.

### 1B: Tool Guardrail Primitives

Status: partial. `ensemble.tool_modes` and `WorkspaceGuard` implement the
Write/Edit and shell gates as library checks; no CLI or MCP tool uses them yet,
and nothing writes evidence.

- Separate `Write` and `Edit`.
- `Write` refuses to overwrite existing files.
- Existing files must go through `Edit`.
- Bash stays gated behind explicit operator opt-in.
- Tool outputs that affect decisions are stored as evidence.

### 1C: Skill Card Support

Status: done, with a larger budget than planned. `ensemble ask` always injects
the `ensemble-technical` card plus keyword matches, each capped at 900
characters.

- Keep the base system prompt small.
- Inject 80-150 token skill cards only when a task needs them.
- Prefer targeted protocols over dumping all rules into every turn.

### 1D: Checkpoint Before Edit

Status: done (`ensemble checkpoint`, `tool_modes.plan_edit`).

- Snapshot file content before any edit-capable flow.
- Store checkpoints under `state/checkpoints/`.
- Refuse edit operations when no checkpoint exists for an existing file.

### 1E: Quality Signals

Status: detection only. `ensemble.quality` flags empty replies, unparsed tool
calls, and repeated tool loops; repair and retry are not implemented.

- Detect empty replies, fake tools, repeated loops, and malformed tool output.
- Attempt output repair before restarting a turn.
- Retry with failing test output when available.

## Substrate Pattern

```text
External coding tool
  + Ensemble llama.cpp profile
  + Ensemble MCP registry
  + Ensemble code-intelligence sidecars
  + Ensemble markdown skills
  + Ensemble checkpoints/evidence folders
  + Docker/local volume boundaries
```
