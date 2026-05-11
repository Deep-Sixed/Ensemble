from __future__ import annotations

import argparse
import json
import sys

from local_first.config import load_config
from local_first.mcp_registry import load_mcp_dir
from local_first.safety import SafetyError, WorkspaceGuard
from local_first.tools.filesystem import list_files, read_file


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(args.env_file)
    guard = WorkspaceGuard(
        config.workspace,
        allow_writes=config.allow_writes,
        allow_shell=config.allow_shell,
    )

    try:
        if args.command == "health":
            from local_first.model import health_check

            ok, message = health_check(config)
            print(("OK: " if ok else "FAIL: ") + message)
            return 0 if ok else 1

        if args.command == "models":
            from local_first.model import fetch_models

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
            from local_first.profiles import list_profiles, load_profile

            for path in list_profiles(args.path):
                profile = load_profile(path)
                print(
                    f"{profile.name}: {profile.provider} {profile.model} "
                    f"({profile.base_url}, ctx={profile.context_window})"
                )
            return 0

        if args.command == "skills":
            from local_first.skills import inject_skill_cards

            print(inject_skill_cards(args.task))
            return 0

        if args.command == "checkpoint":
            from local_first.checkpoints import create_checkpoint

            checkpoint = create_checkpoint(guard, args.path)
            print(f"checkpoint: {checkpoint.snapshot}")
            return 0

        if args.command == "ask":
            from local_first.agent import ask

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
        prog="local-first",
        description="Local-first coding-agent lab with safe workspace boundaries.",
    )
    parser.add_argument("--env-file", help="Optional .env file to load")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health", help="Check the configured OpenAI-compatible endpoint")
    sub.add_parser("models", help="Print /v1/models response")

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

    ask_parser = sub.add_parser("ask", help="Ask the local model one question")
    ask_parser.add_argument("prompt")
    ask_parser.add_argument("--file", help="Include a workspace file as context")

    chat = sub.add_parser("chat", help="Start a simple prompt loop")
    chat.add_argument("--classic", action="store_true", help="Accepted for v1 compatibility")

    return parser


def run_chat(config) -> int:
    from local_first.agent import ask

    print("Local-First chat. Type /quit to exit.")
    while True:
        prompt = input("> ").strip()
        if prompt in {"/q", "/quit", "exit"}:
            return 0
        if not prompt:
            continue
        print(ask(config, prompt))


if __name__ == "__main__":
    raise SystemExit(main())
