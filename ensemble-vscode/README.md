# Ensemble VS Code Extension

Thin handoff from the editor to the `ensemble` CLI. It does not call models.

**Ensemble: Build Context for Task** asks for a task, runs
`ensemble context` against the active workspace folder, then lets you:

- **Copy Context**: copy the rendered context to the clipboard for any agent
  (Pi, Claude Code, Codex, Cursor, ...);
- **Open Packet**: open the full structured JSON packet in an editor.

## Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `ensemble.cliPath` | `ensemble` | Path to the Ensemble CLI |
| `ensemble.tokenBudget` | `12000` | Maximum estimated tokens in the packet |
| `ensemble.semantic` | `true` | LSP enrichment; set `false` for `--no-semantic` |

The CLI runs with `ENSEMBLE_WORKSPACE` set to the workspace folder.

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
