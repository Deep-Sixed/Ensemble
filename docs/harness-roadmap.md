# Harness Roadmap

Local-First is not a generic chat loop pointed at llama.cpp. It is a
small-model-native coding harness optimized for Qwen-class local models.

The thesis:

```text
Qwen3.6-35B-A3B becomes valuable when the surrounding harness is designed for
local-model behavior instead of frontier-model behavior.
```

## Milestones

### 1A: Model Profiles

- Target profile: Qwen3.6-35B-A3B through llama.cpp.
- Smoke profile: tiny/small model for endpoint plumbing only.
- Profiles capture endpoint, context window, token budget, temperature, and
  zero-cost accounting.

### 1B: Tool Guardrails

- Separate `Write` and `Edit`.
- `Write` refuses to overwrite existing files.
- Existing files must go through `Edit`.
- Bash stays gated behind explicit operator opt-in.
- Tool outputs that affect decisions are stored as evidence.

### 1C: Skill Injection

- Keep the base system prompt small.
- Inject 80-150 token skill cards only when a task needs them.
- Prefer targeted protocols over dumping all rules into every turn.

### 1D: Checkpoint Before Edit

- Snapshot file content before any edit-capable flow.
- Store checkpoints under `state/checkpoints/`.
- Refuse edit operations when no checkpoint exists for an existing file.

### 1E: Quality And Retry Loop

- Detect empty replies, fake tools, repeated loops, and malformed tool output.
- Attempt output repair before restarting a turn.
- Retry with failing test output when available.

## Harness Pattern

```text
Base agent loop
  + local llama.cpp provider
  + small-model-specific skills
  + guarded tools
  + repair loops
  + quality monitor
  + constrained bash
  + checkpoints
  + per-model profile
```
