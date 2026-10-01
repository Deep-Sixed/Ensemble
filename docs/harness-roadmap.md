# Substrate Support Roadmap

Ensemble is a lightweight Pi-style coding harness plus a local substrate: a
small tool-calling loop (`harness.py`, `llm.py`, `tools/coding.py`,
`session.py`) alongside model profiles, local inference, MCP config, code
intelligence sidecars, markdown skills, checkpoints, and evidence folders.
External coding tools can still use the substrate directly.

The thesis:

```text
Qwen3.6-35B-A3B becomes valuable when the surrounding substrate and external
tooling are designed for local-model behavior instead of frontier-model behavior.
```

## Milestones

Status: 1A and 1C are implemented. 1B and 1D are exposed as agent tools by
`ensemble agent` (`write` refuses overwrites; `edit` checkpoints first). 1E is
partial: the loop warns on empty replies and stops repeated tool loops, but
automatic repair and retry with failing tests are not implemented.

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
  + Ensemble llama.cpp profile
  + Ensemble MCP registry
  + Ensemble code-intelligence sidecars
  + Ensemble markdown skills
  + Ensemble checkpoints/evidence folders
  + Docker/local volume boundaries
```
