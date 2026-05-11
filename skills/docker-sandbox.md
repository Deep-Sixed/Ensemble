# Docker Sandbox Skill

Use Docker as the default isolation boundary.

- Mount workspaces at `/workspace`.
- Mount models read-only at `/models`.
- Keep secrets in env files or explicit mounts, not images.
- Prefer short-lived tool containers for experiments.
- Keep the model server separate from agent/tool containers.
- Validate Compose config before running heavy services.
