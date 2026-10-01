# Ensemble VS Code Extension

Ensemble sidebar and editor commands for the local llama.cpp server.

Default endpoint (multi-model router):

```text
http://127.0.0.1:8090/v1
```

Single-model Docker stack (`docker-compose.yml`) uses port 8888 instead.

Default model (matches `profiles/auto.json` and the router default):

```text
qwen2.5-coder-7b-instruct-q4_k_m
```

Qwen3 4B is the fast/general alternative and Qwen3.6 35B is explicit
reasoning mode only. Change `ensemble.baseUrl` and `ensemble.model` in
settings to switch.

## Roadmap

```text
0.1.0  Sidebar + ask commands (done)
0.1.1  Status bar health indicator (done)
0.2.0  Patch proposal endpoint (current; `Ensemble: Apply Patch` command present)
0.3.0  Diff preview
0.4.0  Apply patch with checkpoint
0.5.0  Self-hosting reload/test loop
```

Build and package:

```bash
# Node 26.3.0 exact (.nvmrc / mise.toml): use `nvm use`, `fnm use`, or `mise install`
npm install
npm run compile
npm run check         # Biome lint + format
npx @vscode/vsce package
```

Install:

```bash
code --install-extension ensemble-0.2.0.vsix
cursor --install-extension ensemble-0.2.0.vsix
```
