# Substrate Support Roadmap

Local-First is not a replacement agent framework. It is a local substrate that
supports external coding tools with model profiles, local inference, MCP config,
code intelligence sidecars, markdown skills, checkpoints, and evidence folders.

The thesis:

```text
Qwen3.6-35B-A3B becomes valuable when the surrounding substrate and external
tooling are designed for local-model behavior instead of frontier-model behavior.
```

## Milestones

### 1A: Model Profiles

- Target profile: Qwen3.6-35B-A3B through llama.cpp.
- Smoke profile: tiny/small model for endpoint plumbing only.
- Profiles capture endpoint, context window, token budget, temperature, and
  zero-cost accounting.

### 1B: Tool Guardrail Primitives

- Separate `Write` and `Edit`.
- `Write` refuses to overwrite existing files.
- Existing files must go through `Edit`.
- Bash stays gated behind explicit operator opt-in.
- Tool outputs that affect decisions are stored as evidence.

### 1C: Skill Card Support

- Keep the base system prompt small.
- Inject 80-150 token skill cards only when a task needs them.
- Prefer targeted protocols over dumping all rules into every turn.

### 1D: Checkpoint Before Edit

- Snapshot file content before any edit-capable flow.
- Store checkpoints under `state/checkpoints/`.
- Refuse edit operations when no checkpoint exists for an existing file.

### 1E: Quality Signals

- Detect empty replies, fake tools, repeated loops, and malformed tool output.
- Attempt output repair before restarting a turn.
- Retry with failing test output when available.

## Substrate Pattern

```text
External coding tool
  + Local-First llama.cpp profile
  + Local-First MCP registry
  + Local-First code-intelligence sidecars
  + Local-First markdown skills
  + Local-First checkpoints/evidence folders
  + Docker/local volume boundaries
```
