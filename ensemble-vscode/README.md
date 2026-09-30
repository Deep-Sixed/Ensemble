# Ensemble VS Code Extension

Ensemble sidebar and editor commands for the local llama.cpp server.

Default endpoint (multi-model router):

```text
http://127.0.0.1:8090/v1
```

Single-model Docker stack (`docker-compose.yml`) uses port 8888 instead.

Default model:

```text
qwen2.5-coder-7b-instruct-q4_k_m
```

## Settings

| Setting | Default |
|---|---|
| `ensemble.baseUrl` | `http://127.0.0.1:8090/v1` |
| `ensemble.model` | `qwen2.5-coder-7b-instruct-q4_k_m` |
| `ensemble.apiKey` | `ensemble` |
| `ensemble.maxTokens` | `1024` |
| `ensemble.temperature` | `0.2` |

For the single-model stack, set `ensemble.baseUrl` to
`http://127.0.0.1:8888/v1` and `ensemble.model` to the served alias (for
example `qwen3-4b-instruct-2507-ud-q4_k_xl`).

## Roadmap

Current version: 0.2.0. `Ensemble: Apply Patch` is still a placeholder that
points to the CLI; patch proposal is not implemented yet.

```text
0.1.0  Sidebar + ask commands
0.1.1  Status bar health indicator
0.2.0  Patch proposal endpoint
0.3.0  Diff preview
0.4.0  Apply patch with checkpoint
0.5.0  Self-hosting reload/test loop
```

Build and package:

```bash
mise install          # Node 26.3.0 per mise.toml / .nvmrc
mise exec -- npm install
mise exec -- npm run compile
mise exec -- npm run check
mise exec -- npx @vscode/vsce package
```

Install:

```bash
code --install-extension ensemble-0.2.0.vsix
cursor --install-extension ensemble-0.2.0.vsix
```
