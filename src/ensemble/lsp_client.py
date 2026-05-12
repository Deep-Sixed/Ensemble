from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

Json = dict[str, Any]


def path_to_file_uri(path: str | Path) -> str:
    return Path(path).resolve().as_uri()


def file_uri_to_path(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return uri
    return str(Path(unquote(parsed.path)).resolve())


def _lsp_position(line: int, character: int) -> Json:
    if line < 0 or character < 0:
        raise ValueError("line and character must be 0-based non-negative integers")
    return {"line": line, "character": character}


@dataclass(frozen=True)
class LspServerConfig:
    name: str
    extensions: tuple[str, ...]
    command: tuple[str, ...]
    language_id: str
    initialization_options: Json | None = None
    settings: Json | None = None

    def matches(self, file_path: str | Path) -> bool:
        suffix = Path(file_path).suffix.lower()
        return suffix in {extension.lower() for extension in self.extensions}


@dataclass(frozen=True)
class LspLocation:
    uri: str
    start_line: int
    start_character: int
    end_line: int
    end_character: int

    @classmethod
    def from_lsp(cls, value: Json) -> "LspLocation":
        if "targetUri" in value:
            uri = value["targetUri"]
            range_value = value.get("targetSelectionRange") or value.get("targetRange")
        else:
            uri = value["uri"]
            range_value = value["range"]
        if range_value is None:
            raise LspProtocolError(f"LSP location is missing a range: {value}")

        return cls(
            uri=uri,
            start_line=int(range_value["start"]["line"]),
            start_character=int(range_value["start"]["character"]),
            end_line=int(range_value["end"]["line"]),
            end_character=int(range_value["end"]["character"]),
        )

    @property
    def file_path(self) -> str:
        return file_uri_to_path(self.uri)

    def to_dict(self) -> Json:
        payload = asdict(self)
        payload["file_path"] = self.file_path
        return payload

    def __str__(self) -> str:
        return f"{self.file_path}:{self.start_line + 1}:{self.start_character + 1}"


@dataclass(frozen=True)
class LspDocumentSymbol:
    name: str
    kind: int
    start_line: int
    start_character: int
    end_line: int
    end_character: int
    selection_start_line: int
    selection_start_character: int
    children: list["LspDocumentSymbol"]

    @classmethod
    def from_lsp(cls, value: Json) -> "LspDocumentSymbol":
        range_value = value["range"]
        selection_range = value["selectionRange"]
        return cls(
            name=str(value["name"]),
            kind=int(value["kind"]),
            start_line=int(range_value["start"]["line"]),
            start_character=int(range_value["start"]["character"]),
            end_line=int(range_value["end"]["line"]),
            end_character=int(range_value["end"]["character"]),
            selection_start_line=int(selection_range["start"]["line"]),
            selection_start_character=int(selection_range["start"]["character"]),
            children=[
                cls.from_lsp(child)
                for child in value.get("children", [])
                if isinstance(child, dict)
            ],
        )

    def to_dict(self) -> Json:
        payload = asdict(self)
        payload["children"] = [child.to_dict() for child in self.children]
        return payload


class LspProtocolError(RuntimeError):
    pass


class LspServerStoppedError(RuntimeError):
    pass


class LspClient:
    def __init__(self, config: LspServerConfig | None = None, root: str | Path = ".") -> None:
        self.config = config or LspServerConfig(
            name="pyright",
            extensions=(".py",),
            command=("pyright-langserver", "--stdio"),
            language_id="python",
        )
        self.root = Path(root).resolve()
        self.proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._opened_documents: dict[str, int] = {}
        self._write_lock = asyncio.Lock()
        self._initialized = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def start(self) -> None:
        if self.is_running:
            return

        self.proc = await asyncio.create_subprocess_exec(
            *self.config.command,
            cwd=str(self.root),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        asyncio.create_task(self._drain_stderr())
        await self._initialize()

    async def stop(self) -> None:
        if not self.proc:
            return

        try:
            await self.request("shutdown", None, timeout=5)
            await self.notify("exit", None)
        except Exception:
            pass

        if self._reader_task:
            self._reader_task.cancel()

        if self.proc.returncode is None:
            self.proc.terminate()
            try:
                await asyncio.wait_for(self.proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                self.proc.kill()
                await self.proc.wait()

        self.proc = None
        self._opened_documents.clear()
        self._initialized.clear()

    async def notify(self, method: str, params: Any = None) -> None:
        message: Json = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        await self._send(message)

    async def request(self, method: str, params: Any = None, timeout: float = 15) -> Any:
        self._raise_if_stopped()
        self._request_id += 1
        request_id = self._request_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[request_id] = future

        message: Json = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            message["params"] = params

        await self._send(message)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(request_id, None)
            future.cancel()
            raise

    async def did_open(self, path: str | Path) -> str:
        self._raise_if_stopped()
        await self._initialized.wait()
        file_path = Path(path).resolve()
        file_uri = path_to_file_uri(file_path)
        if file_uri in self._opened_documents:
            return file_uri

        text = file_path.read_text(encoding="utf-8", errors="replace")
        await self.notify(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": file_uri,
                    "languageId": self.config.language_id,
                    "version": 1,
                    "text": text,
                }
            },
        )
        self._opened_documents[file_uri] = 1
        return file_uri

    async def hover(self, path: str | Path, line: int, character: int) -> str | None:
        file_uri = await self.did_open(path)
        result = await self.request(
            "textDocument/hover",
            {
                "textDocument": {"uri": file_uri},
                "position": _lsp_position(line, character),
            },
        )
        if not result:
            return None
        return self._stringify_hover(result.get("contents"))

    async def definition(self, path: str | Path, line: int, character: int) -> list[LspLocation]:
        file_uri = await self.did_open(path)
        result = await self.request(
            "textDocument/definition",
            {
                "textDocument": {"uri": file_uri},
                "position": _lsp_position(line, character),
            },
        )
        return self._locations_from_result(result)

    async def references(
        self,
        path: str | Path,
        line: int,
        character: int,
        include_declaration: bool = True,
    ) -> list[LspLocation]:
        file_uri = await self.did_open(path)
        result = await self.request(
            "textDocument/references",
            {
                "textDocument": {"uri": file_uri},
                "position": _lsp_position(line, character),
                "context": {"includeDeclaration": include_declaration},
            },
        )
        return self._locations_from_result(result)

    async def document_symbols(self, path: str | Path) -> list[LspDocumentSymbol | LspLocation]:
        file_uri = await self.did_open(path)
        result = await self.request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": file_uri}},
        )
        return self._document_symbols_from_result(result)

    async def _initialize(self) -> None:
        root_uri = path_to_file_uri(self.root)
        params: Json = {
            "processId": os.getpid(),
            "rootUri": root_uri,
            "workspaceFolders": [{"uri": root_uri, "name": self.root.name}],
            "capabilities": {
                "textDocument": {
                    "hover": {
                        "dynamicRegistration": False,
                        "contentFormat": ["markdown", "plaintext"],
                    },
                    "definition": {"dynamicRegistration": False, "linkSupport": True},
                    "references": {"dynamicRegistration": False},
                    "documentSymbol": {
                        "dynamicRegistration": False,
                        "hierarchicalDocumentSymbolSupport": True,
                    },
                    "synchronization": {"didSave": True, "dynamicRegistration": False},
                },
                "workspace": {"workspaceFolders": True},
            },
            "clientInfo": {"name": "ensemble-lsp", "version": "0.1.0"},
        }
        if self.config.initialization_options is not None:
            params["initializationOptions"] = self.config.initialization_options

        await self.request("initialize", params, timeout=30)
        await self.notify("initialized", {})

        if self.config.settings:
            await self.notify("workspace/didChangeConfiguration", {"settings": self.config.settings})

        self._initialized.set()

    async def _send(self, message: Json) -> None:
        self._raise_if_stopped()
        if not self.proc or not self.proc.stdin:
            raise LspServerStoppedError("LSP server is not running")

        body = json.dumps(message, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")

        async with self._write_lock:
            self.proc.stdin.write(header + body)
            await self.proc.stdin.drain()

    async def _read_loop(self) -> None:
        if not self.proc or not self.proc.stdout:
            raise RuntimeError("LSP server is not running")

        try:
            while True:
                message = await self._read()
                self._handle_message(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._initialized.clear()
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(exc)
            self._pending.clear()

    async def _read(self) -> Json:
        if not self.proc or not self.proc.stdout:
            raise LspServerStoppedError("LSP server is not running")

        headers: dict[str, str] = {}
        while True:
            line = await self.proc.stdout.readline()
            if line == b"":
                raise LspServerStoppedError("LSP server closed stdout")
            if line in (b"\r\n", b"\n"):
                break

            key, value = line.decode("ascii").split(":", 1)
            headers[key.lower()] = value.strip()

        content_length = int(headers["content-length"])
        body = await self.proc.stdout.readexactly(content_length)
        return json.loads(body.decode("utf-8"))

    def _handle_message(self, message: Json) -> None:
        if "id" not in message or ("result" not in message and "error" not in message):
            return

        request_id = int(message["id"])
        future = self._pending.pop(request_id, None)
        if future is None or future.done():
            return

        if "error" in message:
            future.set_exception(LspProtocolError(str(message["error"])))
        else:
            future.set_result(message.get("result"))

    def _raise_if_stopped(self) -> None:
        if not self.proc:
            raise LspServerStoppedError("LSP server is not running")
        if self.proc.returncode is not None:
            raise LspServerStoppedError(
                f"LSP server exited with status {self.proc.returncode}"
            )

    async def _drain_stderr(self) -> None:
        if not self.proc or not self.proc.stderr:
            return

        while True:
            line = await self.proc.stderr.readline()
            if not line:
                return

    @staticmethod
    def _locations_from_result(result: Any) -> list[LspLocation]:
        if result is None:
            return []
        if isinstance(result, dict):
            result = [result]
        return [LspLocation.from_lsp(item) for item in result]

    @staticmethod
    def _document_symbols_from_result(result: Any) -> list[LspDocumentSymbol | LspLocation]:
        if result is None:
            return []
        if not isinstance(result, list):
            raise LspProtocolError(f"Unexpected documentSymbol result: {result}")

        symbols: list[LspDocumentSymbol | LspLocation] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            if "location" in item and isinstance(item["location"], dict):
                symbols.append(LspLocation.from_lsp(item["location"]))
            else:
                symbols.append(LspDocumentSymbol.from_lsp(item))
        return symbols

    @staticmethod
    def _stringify_hover(contents: Any) -> str:
        if contents is None:
            return ""
        if isinstance(contents, str):
            return contents
        if isinstance(contents, dict):
            return str(contents.get("value") or contents.get("language") or contents)
        if isinstance(contents, list):
            return "\n\n".join(LspClient._stringify_hover(item) for item in contents)
        return str(contents)


class LspServerManager:
    def __init__(
        self,
        configs: list[LspServerConfig] | None = None,
        workspace_markers: tuple[str, ...] | None = None,
    ) -> None:
        self.configs = configs or default_configs()
        self.workspace_markers = workspace_markers or (
            ".git",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
            "*.sln",
        )
        self._clients: dict[tuple[str, str], LspClient] = {}
        self._lock = asyncio.Lock()

    def config_for_file(self, file_path: str | Path) -> LspServerConfig | None:
        for config in self.configs:
            if config.matches(file_path):
                return config
        return None

    def find_workspace_root(self, file_path: str | Path) -> Path:
        path = Path(file_path).resolve()
        directory = path if path.is_dir() else path.parent

        for candidate in (directory, *directory.parents):
            for marker in self.workspace_markers:
                if "*" in marker:
                    if any(candidate.glob(marker)):
                        return candidate
                elif (candidate / marker).exists():
                    return candidate
        return directory

    async def get_client(self, file_path: str | Path) -> LspClient | None:
        path = Path(file_path).resolve()
        config = self.config_for_file(path)
        if config is None:
            return None

        root = self.find_workspace_root(path)
        key = (config.name, str(root))

        async with self._lock:
            client = self._clients.get(key)
            if client is not None and not client.is_running:
                await client.stop()
                client = None
                self._clients.pop(key, None)
            if client is None:
                client = LspClient(config=config, root=root)
                await client.start()
                self._clients[key] = client
            return client

    async def hover(self, file_path: str | Path, line: int, character: int) -> str | None:
        client = await self.get_client(file_path)
        if client is None:
            return None
        return await client.hover(file_path, line, character)

    async def definition(self, file_path: str | Path, line: int, character: int) -> list[LspLocation]:
        client = await self.get_client(file_path)
        if client is None:
            return []
        return await client.definition(file_path, line, character)

    async def references(self, file_path: str | Path, line: int, character: int) -> list[LspLocation]:
        client = await self.get_client(file_path)
        if client is None:
            return []
        return await client.references(file_path, line, character)

    async def document_symbols(
        self,
        file_path: str | Path,
    ) -> list[LspDocumentSymbol | LspLocation]:
        client = await self.get_client(file_path)
        if client is None:
            return []
        return await client.document_symbols(file_path)

    async def close_all(self) -> None:
        clients = list(self._clients.values())
        self._clients.clear()
        await asyncio.gather(*(client.stop() for client in clients), return_exceptions=True)

    async def __aenter__(self) -> "LspServerManager":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        await self.close_all()


def default_configs() -> list[LspServerConfig]:
    return [
        LspServerConfig(
            name="pyright",
            extensions=(".py",),
            command=("pyright-langserver", "--stdio"),
            language_id="python",
        ),
        LspServerConfig(
            name="typescript-language-server",
            extensions=(".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
            command=("typescript-language-server", "--stdio"),
            language_id="typescript",
        ),
        LspServerConfig(
            name="rust-analyzer",
            extensions=(".rs",),
            command=("rust-analyzer",),
            language_id="rust",
        ),
        LspServerConfig(
            name="clangd",
            extensions=(".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"),
            command=("clangd", "--background-index"),
            language_id="cpp",
        ),
        LspServerConfig(
            name="omnisharp",
            extensions=(".cs",),
            command=("OmniSharp", "--languageserver"),
            language_id="csharp",
        ),
    ]


def flatten_document_symbols(
    symbols: list[LspDocumentSymbol | LspLocation],
) -> list[Json]:
    flattened: list[Json] = []

    def visit(symbol: LspDocumentSymbol, container_name: str | None = None) -> None:
        item = symbol.to_dict()
        item.pop("children", None)
        item["container_name"] = container_name
        flattened.append(item)

        for child in symbol.children:
            visit(child, symbol.name)

    for symbol in symbols:
        if isinstance(symbol, LspDocumentSymbol):
            visit(symbol)
        else:
            flattened.append(symbol.to_dict())

    return flattened
