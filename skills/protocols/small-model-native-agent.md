# Small-Model-Native Agent Protocol

Ensemble is optimized around scaffold-model fit.

- Keep prompts compact and specific.
- Inject skills only when they match the task.
- Prefer code graph and filesystem evidence over broad context dumps.
- Use checkpoints before any edit-capable flow.
- Repair malformed tool output instead of restarting the whole turn.
- Keep context windows controlled, especially on local hardware.
- Use smoke profiles for plumbing, not quality judgments.
