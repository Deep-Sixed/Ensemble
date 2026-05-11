# Code Intelligence Tools

This folder tracks Local-First sidecar integrations for repo intelligence tools.

`code-review-graph` is the first target. It should be installed outside the app
runtime, preferably with `pipx`, and should build its graph into the local
`.code-review-graph/` directory.

Local-First treats code intelligence as replaceable dev tooling. It is not part
of the app runtime.
