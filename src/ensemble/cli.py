from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ensemble.config import load_config
from ensemble.mcp_registry import load_mcp_dir
from ensemble.safety import SafetyError, WorkspaceGuard
from ensemble.tools.filesystem import list_files, read_file


def _cli_profile_arg(value: str) -> str:
    name = value.strip()
    if not name:
        raise argparse.ArgumentTypeError("profile name must not be empty")
    return name


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.env_file, profile_override=getattr(args, "profile", None))
    guard = WorkspaceGuard(
        config.workspace,
        allow_writes=config.allow_writes,
        allow_shell=config.allow_shell,
    )

    try:
        if args.command == "health":
            from ensemble.model import health_check

            ok, message = health_check(config)
            print(("OK: " if ok else "FAIL: ") + message)
            return 0 if ok else 1

        if args.command == "models":
            from ensemble.model import fetch_models

            print(json.dumps(fetch_models(config), indent=2))
            return 0

        if args.command == "files":
            for path in list_files(guard, args.path, limit=args.limit):
                print(path)
            return 0

        if args.command == "read":
            print(read_file(guard, args.path, max_bytes=config.max_file_bytes))
            return 0

        if args.command == "mcp":
            for server in load_mcp_dir(args.path):
                state = "enabled" if server.enabled else "disabled"
                print(f"{server.name}: {state} ({server.command})")
            return 0

        if args.command == "profiles":
            from ensemble.profiles import list_profiles, load_profile

            for path in list_profiles(args.path):
                profile = load_profile(path)
                print(
                    f"{profile.name}: {profile.provider} {profile.model} "
                    f"({profile.base_url}, ctx={profile.context_window})"
                )
            return 0

        if args.command == "skills":
            from ensemble.skills import inject_skill_cards

            print(inject_skill_cards(args.task))
            return 0

        if args.command == "checkpoint":
            from ensemble.checkpoints import create_checkpoint

            checkpoint = create_checkpoint(guard, args.path)
            print(f"checkpoint: {checkpoint.snapshot}")
            return 0

        if args.command == "lsp":
            asyncio.run(
                _run_lsp_action(
                    args.action,
                    args.file,
                    getattr(args, "line", None),
                    getattr(args, "character", None),
                    flat=getattr(args, "flat", False),
                )
            )
            return 0

        if args.command == "symbols":
            asyncio.run(_run_symbols_action(args.symbols_action, args.path, args.out))
            return 0

        if args.command == "graph":
            _run_graph_action(args.graph_action, args.path, args.out)
            return 0

        if args.command == "ask":
            from ensemble.agent import ask

            context = None
            if args.file:
                context = read_file(guard, args.file, max_bytes=config.max_file_bytes)
            print(ask(config, args.prompt, context=context))
            return 0

        if args.command == "chat":
            return run_chat(config)

        parser.print_help()
        return 1
    except SafetyError as exc:
        print(f"Safety error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ensemble",
        description="Local-first coding-agent lab with safe workspace boundaries.",
    )
    parser.add_argument("--env-file", help="Optional .env file to load")
    sub = parser.add_subparsers(dest="command")

    health = sub.add_parser(
        "health",
        help="Check the OpenAI-compatible /v1/models endpoint (env defaults, or profile base_url with --profile)",
    )
    health.add_argument(
        "--profile",
        type=_cli_profile_arg,
        help="Use this profile's base_url and auth for the check (overrides ENSEMBLE_LLM_* for this command)",
    )

    models = sub.add_parser("models", help="Print /v1/models response")
    models.add_argument(
        "--profile",
        type=_cli_profile_arg,
        help="Use this profile's base_url and auth (overrides ENSEMBLE_LLM_* for this command)",
    )

    files = sub.add_parser("files", help="List workspace files read-only")
    files.add_argument("path", nargs="?", default=".")
    files.add_argument("--limit", type=int, default=200)

    read = sub.add_parser("read", help="Read one workspace file")
    read.add_argument("path")

    mcp = sub.add_parser("mcp", help="List MCP server configs")
    mcp.add_argument("path", nargs="?", default="mcp")

    profiles = sub.add_parser("profiles", help="List local model profiles")
    profiles.add_argument("path", nargs="?", default=".")

    skills = sub.add_parser("skills", help="Preview dynamic skill cards for a task")
    skills.add_argument("task")

    checkpoint = sub.add_parser("checkpoint", help="Create a file checkpoint")
    checkpoint.add_argument("path")

    lsp = sub.add_parser("lsp", help="Query optional LSP code intelligence")
    lsp_sub = lsp.add_subparsers(dest="action", required=True)
    for name in ("hover", "definition", "references"):
        action = lsp_sub.add_parser(name, help=f"Run textDocument/{name}")
        action.add_argument("file")
        action.add_argument("line", type=int, help="Zero-based line number")
        action.add_argument("character", type=int, help="Zero-based character offset")
    symbols = lsp_sub.add_parser("symbols", help="Run textDocument/documentSymbol")
    symbols.add_argument("--flat", action="store_true", help="Flatten hierarchical symbols")
    symbols.add_argument("file")

    symbols_root = sub.add_parser("symbols", help="Build durable symbol indexes")
    symbols_sub = symbols_root.add_subparsers(dest="symbols_action", required=True)
    symbols_index = symbols_sub.add_parser("index", help="Index symbols under a file or directory")
    symbols_index.add_argument("path")
    symbols_index.add_argument(
        "--out",
        default=".ensemble/symbols.jsonl",
        help="JSONL output path",
    )

    graph = sub.add_parser("graph", help="Build graph facts from durable indexes")
    graph_sub = graph.add_subparsers(dest="graph_action", required=True)
    graph_symbols = graph_sub.add_parser("symbols", help="Build graph facts from a symbol index")
    graph_symbols.add_argument("path")
    graph_symbols.add_argument(
        "--out",
        default=".ensemble/symbol-graph.jsonl",
        help="JSONL output path",
    )

    ask_parser = sub.add_parser("ask", help="Ask the local model one question")
    ask_parser.add_argument(
        "--profile",
        type=_cli_profile_arg,
        help="Use this profile's base_url and auth (overrides ENSEMBLE_LLM_* for this command)",
    )
    ask_parser.add_argument("prompt")
    ask_parser.add_argument("--file", help="Include a workspace file as context")

    chat = sub.add_parser("chat", help="Start a simple prompt loop")
    chat.add_argument(
        "--profile",
        type=_cli_profile_arg,
        help="Use this profile's base_url and auth (overrides ENSEMBLE_LLM_* for this command)",
    )
    chat.add_argument("--classic", action="store_true", help="Accepted for v1 compatibility")

    return parser


async def _run_lsp_action(
    action: str,
    file: str,
    line: int | None = None,
    character: int | None = None,
    *,
    flat: bool = False,
) -> None:
    from ensemble.lsp_client import (
        LspDocumentSymbol,
        LspLocation,
        LspServerManager,
        flatten_document_symbols,
    )

    async with LspServerManager() as manager:
        if action == "hover":
            if line is None or character is None:
                raise ValueError("hover requires line and character")
            result = await manager.hover(file, line, character)
        elif action == "definition":
            if line is None or character is None:
                raise ValueError("definition requires line and character")
            result = await manager.definition(file, line, character)
        elif action == "references":
            if line is None or character is None:
                raise ValueError("references requires line and character")
            result = await manager.references(file, line, character)
        elif action == "symbols":
            result = await manager.document_symbols(file)
            if flat:
                result = flatten_document_symbols(result)
        else:
            raise ValueError(f"Unknown LSP action: {action}")

    if isinstance(result, list):
        result = [
            item.to_dict() if isinstance(item, LspLocation | LspDocumentSymbol) else item
            for item in result
        ]
    print(json.dumps(result, indent=2))


async def _run_symbols_action(action: str, path: str, out: str) -> None:
    if action != "index":
        raise ValueError(f"Unknown symbols action: {action}")

    from ensemble.indexing.symbol_index import write_symbol_index

    count = await write_symbol_index(path, out)
    print(f"indexed {count} symbol(s) -> {out}")


def _run_graph_action(action: str, path: str, out: str) -> None:
    if action != "symbols":
        raise ValueError(f"Unknown graph action: {action}")

    from ensemble.graph.symbol_graph import write_symbol_graph

    count = write_symbol_graph(path, out)
    print(f"wrote {count} graph fact(s) -> {out}")


def run_chat(config) -> int:
    from ensemble.agent import ask

    print("Ensemble chat. Type /quit to exit.")
    while True:
        prompt = input("> ").strip()
        if prompt in {"/q", "/quit", "exit"}:
            return 0
        if not prompt:
            continue
        print(ask(config, prompt))


if __name__ == "__main__":
    raise SystemExit(main())
