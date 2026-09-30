from __future__ import annotations

import argparse
import asyncio
import json
import sys

from ensemble.client import EnsembleClient
from ensemble.config import load_config
from ensemble.safety import SafetyError, WorkspaceGuard
from ensemble.tools.filesystem import list_files, read_file


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.env_file)
    guard = WorkspaceGuard(config.workspace, allow_writes=False, allow_shell=False)
    client = EnsembleClient(config)

    try:
        if args.command == "context":
            if args.no_semantic:
                from ensemble.context import build_context_packet

                packet = build_context_packet(
                    args.task,
                    guard,
                    token_budget=args.token_budget or config.context_token_budget,
                    max_file_bytes=config.max_file_bytes,
                    max_files=args.max_files,
                    skill_root=args.skills,
                )
            else:
                from ensemble.semantic import build_semantic_context_packet

                packet = asyncio.run(
                    build_semantic_context_packet(
                        args.task,
                        guard,
                        token_budget=args.token_budget or config.context_token_budget,
                        max_file_bytes=config.max_file_bytes,
                        max_files=args.max_files,
                        skill_root=args.skills,
                    )
                )
            print(json.dumps(packet.to_dict(), indent=2))
            return 0

        if args.command == "health":
            ok, message = client.health()
            print(("OK: " if ok else "FAIL: ") + message)
            return 0 if ok else 1

        if args.command == "models":
            print(json.dumps(client.models(), indent=2))
            return 0

        if args.command == "files":
            for path in list_files(guard, args.path, limit=args.limit):
                print(path)
            return 0

        if args.command == "read":
            print(read_file(guard, args.path, max_bytes=config.max_file_bytes))
            return 0

        if args.command == "skills":
            from ensemble.skills import inject_skill_cards
            print(inject_skill_cards(args.task))
            return 0

        if args.command == "checkpoint":
            from ensemble.checkpoints import create_checkpoint
            checkpoint = create_checkpoint(guard, args.path, config.checkpoint_dir)
            print(f"checkpoint: {checkpoint.snapshot}")
            return 0

        if args.command == "lsp":
            asyncio.run(
                _run_lsp_action(
                    guard,
                    args.action,
                    args.file,
                    getattr(args, "line", None),
                    getattr(args, "character", None),
                    flat=getattr(args, "flat", False),
                )
            )
            return 0

        if args.command == "symbols":
            asyncio.run(_run_symbols_action(guard, args.path, args.out))
            return 0

        if args.command == "graph":
            _run_graph_action(guard, args.path, args.out)
            return 0

        if args.command == "ask":
            context = None
            if args.file:
                context = read_file(guard, args.file, max_bytes=config.max_file_bytes)
            print(client.ask(args.prompt, context=context))
            return 0

        if args.command == "chat":
            return run_chat(client)

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
        description="Repository intelligence and code-context engine.",
    )
    parser.add_argument("--env-file", help="Optional .env file to load")
    sub = parser.add_subparsers(dest="command")

    context = sub.add_parser("context", help="Assemble a structured code-context packet")
    context.add_argument("task", help="Task or question the context should support")
    context.add_argument("--token-budget", type=int, help="Maximum estimated context tokens")
    context.add_argument("--max-files", type=int, default=40, help="Maximum ranked files to consider")
    context.add_argument("--skills", default="skills", help="Skill-card directory")
    context.add_argument(
        "--no-semantic",
        action="store_true",
        help="Skip LSP/symbol enrichment and use workspace/Git context only",
    )

    sub.add_parser("health", help="Check the configured downstream endpoint")
    sub.add_parser("models", help="Print the endpoint's /v1/models response")

    files = sub.add_parser("files", help="List workspace files read-only")
    files.add_argument("path", nargs="?", default=".")
    files.add_argument("--limit", type=int, default=200)

    read = sub.add_parser("read", help="Read one workspace file")
    read.add_argument("path")

    skills = sub.add_parser("skills", help="Preview task-relevant skill cards")
    skills.add_argument("task")

    checkpoint = sub.add_parser("checkpoint", help="Create a local pre-edit checkpoint")
    checkpoint.add_argument("path")

    lsp = sub.add_parser("lsp", help="Query optional LSP code intelligence")
    lsp_sub = lsp.add_subparsers(dest="action", required=True)
    for name in ("hover", "definition", "references"):
        action = lsp_sub.add_parser(name)
        action.add_argument("file")
        action.add_argument("line", type=int)
        action.add_argument("character", type=int)
    symbols = lsp_sub.add_parser("symbols")
    symbols.add_argument("--flat", action="store_true")
    symbols.add_argument("file")

    symbols_root = sub.add_parser("symbols", help="Build a disposable local symbol index")
    symbols_root.add_argument("path")
    symbols_root.add_argument("--out", default=".ensemble/symbols.jsonl")

    graph = sub.add_parser("graph", help="Build lightweight facts from a symbol index")
    graph.add_argument("path")
    graph.add_argument("--out", default=".ensemble/symbol-graph.jsonl")

    ask_parser = sub.add_parser("ask", help="Diagnostic request to the downstream endpoint")
    ask_parser.add_argument("prompt")
    ask_parser.add_argument("--file", help="Include one workspace file as context")

    sub.add_parser("chat", help="Diagnostic prompt loop")
    return parser


async def _run_lsp_action(
    guard: WorkspaceGuard,
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

    resolved_file = guard.resolve_read_path(file)
    async with LspServerManager() as manager:
        if action == "hover":
            if line is None or character is None:
                raise ValueError("hover requires line and character")
            result = await manager.hover(resolved_file, line, character)
        elif action == "definition":
            if line is None or character is None:
                raise ValueError("definition requires line and character")
            result = await manager.definition(resolved_file, line, character)
        elif action == "references":
            if line is None or character is None:
                raise ValueError("references requires line and character")
            result = await manager.references(resolved_file, line, character)
        else:
            result = await manager.document_symbols(resolved_file)
            if flat:
                result = flatten_document_symbols(result)

    if isinstance(result, list):
        result = [
            item.to_dict() if isinstance(item, (LspLocation, LspDocumentSymbol)) else item
            for item in result
        ]
    print(json.dumps(result, indent=2))


async def _run_symbols_action(guard: WorkspaceGuard, path: str, out: str) -> None:
    from ensemble.indexing.symbol_index import write_symbol_index

    root = guard.resolve_read_path(path)
    output = guard.resolve_derived_path(out)
    count = await write_symbol_index(root, output, repo_root=guard.root)
    print(f"indexed {count} symbol(s) -> {output}")


def _run_graph_action(guard: WorkspaceGuard, path: str, out: str) -> None:
    from ensemble.graph.symbol_graph import write_symbol_graph

    source = guard.resolve_read_path(path)
    output = guard.resolve_derived_path(out)
    count = write_symbol_graph(source, output)
    print(f"wrote {count} graph fact(s) -> {output}")


def run_chat(client: EnsembleClient) -> int:
    print("Ensemble diagnostic chat. Type /quit to exit.")
    while True:
        prompt = input("> ").strip()
        if prompt in {"/q", "/quit", "exit"}:
            return 0
        if prompt:
            print(client.ask(prompt))


if __name__ == "__main__":
    raise SystemExit(main())
