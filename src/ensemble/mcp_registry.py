from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class McpServer:
    name: str
    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    enabled: bool
    notes: str = ""


def load_mcp_file(path: str | Path) -> list[McpServer]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    servers = payload.get("mcpServers", {})
    return [_server_from_payload(name, data) for name, data in servers.items()]


def load_mcp_dir(path: str | Path) -> list[McpServer]:
    root = Path(path)
    servers: list[McpServer] = []
    for config_file in sorted(root.glob("*.json")):
        servers.extend(load_mcp_file(config_file))
    return servers


def enabled_servers(path: str | Path) -> list[McpServer]:
    return [server for server in load_mcp_dir(path) if server.enabled]


def _server_from_payload(name: str, data: dict[str, Any]) -> McpServer:
    return McpServer(
        name=name,
        command=str(data["command"]),
        args=tuple(str(arg) for arg in data.get("args", [])),
        env={str(k): str(v) for k, v in data.get("env", {}).items()},
        enabled=bool(data.get("enabled", True)),
        notes=str(data.get("notes", "")),
    )
