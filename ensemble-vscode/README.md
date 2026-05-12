# Ensemble VS Code Extension

Ensemble sidebar and editor commands for the local llama.cpp server.

Default endpoint:

```text
http://127.0.0.1:8888/v1
```

Default model:

```text
qwen3-4b-instruct-2507-ud-q4_k_xl
```

## Roadmap

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
npm install
npm run compile
npx @vscode/vsce package
```

Install:

```bash
code --install-extension ensemble-0.1.1.vsix
cursor --install-extension ensemble-0.1.1.vsix
```
