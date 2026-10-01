# Code Intelligence Tools

This folder tracks Ensemble sidecar integrations for repo intelligence tools.

`code-review-graph` is the first target. See the README section "Code
Intelligence: code-review-graph" and `mcp/code-review-graph.json` for setup and
MCP wiring. It should be installed outside the app
runtime, preferably with `pipx`, and should build its graph into the local
`.code-review-graph/` directory.

Ensemble treats code intelligence as replaceable dev tooling. It is not part
of the app runtime.
