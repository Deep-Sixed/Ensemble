# Tau Reference Notes

Reviewed: [huggingface/tau](https://github.com/huggingface/tau) at `ba58896`
(2026-09-30, `tau-ai` 0.4.6).

Ensemble stays a **substrate** for external coding tools (see
`harness-roadmap.md`). It does not become a harness like Tau. These notes record
the few Tau ideas worth borrowing and the parts to leave alone.

## What Tau is

A Python coding-agent harness in three layers:

```text
tau_coding  ->  tau_agent  ->  tau_ai
(app, TUI)      (agent core)    (providers)
```

The core (`tau_agent`, `loop.py` 376 lines, `harness.py` 259 lines) is small
and must not import CLI, Rich, or Textual. `tau_coding` is much larger (OAuth,
extension runtime, TUI, session export, local backends).

## Borrow

1. **Interrupted tool-call repair** (`tau_agent/tool_history.py`,
   `harness.py`). If a transcript ends with a tool call that never returned,
   append an error result ("Tool call interrupted by user") so later turns are
   not corrupted. Apply this if Ensemble stores tool-call transcripts.
2. **Typed, provider-neutral events.** Consumers read an event stream instead of
   the core rendering UI. Relevant if `ensemble.agent.ask` ever streams.
3. **JSONL sessions.** Append-only entries with resume, branch, and compaction
   (`tau_agent/session/`). Fits `state/` and `state/evidence` as a format; do
   not add a session database.
4. **Local-backend boundary.** Tau keeps local inference out of the agent core.
   Backends expose typed configuration, status, progress, diagnostics, and
   capabilities. For Ensemble: profiles and the router report status and
   capabilities; process lifecycle stays in Docker/compose.
5. **Tool hooks.** `before_tool_call` can block a call and `after_tool_call` can
   rewrite its result. This is a natural place for the operator-approval gate
   if Ensemble ever mediates tool calls.

## Leave alone

- Steering and follow-up queues, `cancel()`: harness concerns that belong to the
  external coding tool.
- TUI, themes, OAuth, extension runtime, model catalogs, per-provider adapters.
- Tau's `tau_ai` provider layer: Ensemble targets one OpenAI-compatible
  endpoint (profiles, router) via `ensemble.model`.

## Caveats

- Tau's "minimal" applies to the core only; the app layer is several MB.
- The "reusable brain" wording is in `dev-notes/design/01-architecture.md`
  (`AgentHarness` / `AgentSession` / TUI), not in the public architecture page
  (`website/content/internals/architecture.md`).
- Safety defaults differ: Ensemble keeps `ENSEMBLE_ALLOW_WRITES=false` and
  `ENSEMBLE_ALLOW_SHELL=false`. Do not adopt Tau tool behavior without keeping
  those gates.
