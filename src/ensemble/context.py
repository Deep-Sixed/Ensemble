from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ensemble.budget import ContextBudget
from ensemble.git_context import GitContext, collect_git_context
from ensemble.ranking import RankedFile, rank_files
from ensemble.safety import WorkspaceGuard
from ensemble.skills import inject_skill_cards
from ensemble.workspace import WorkspaceFile, discover_workspace_files


@dataclass(frozen=True)
class ContextPacket:
    schema_version: int
    task: str
    workspace: str
    files: list[dict[str, Any]]
    symbols: list[dict[str, Any]]
    definitions: list[dict[str, Any]]
    references: list[dict[str, Any]]
    git_changes: dict[str, Any]
    instructions: list[str]
    context: str
    token_estimate: int
    token_budget: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_context_packet(
    task: str,
    guard: WorkspaceGuard,
    *,
    token_budget: int = 12_000,
    max_file_bytes: int = 200_000,
    max_files: int = 40,
    skill_root: str | Path = "skills",
) -> ContextPacket:
    budget = ContextBudget(token_budget)
    discovered = discover_workspace_files(
        guard,
        max_file_bytes=max_file_bytes,
    )
    git_context = collect_git_context(guard.root)
    ranked = rank_files(task, discovered, changed_paths=git_context.changed_paths)[:max_files]

    rendered_parts: list[str] = []
    selected_files: list[dict[str, Any]] = []
    truncated = False

    instructions_text = inject_skill_cards(task, skill_root)
    instructions = [instructions_text] if instructions_text else []
    if instructions_text:
        accepted, was_truncated = budget.take(instructions_text)
        if accepted:
            rendered_parts.append(f"[instructions]\n{accepted}")
        truncated = truncated or was_truncated

    git_text = git_context.render()
    if git_text:
        accepted, was_truncated = budget.take(git_text)
        if accepted:
            rendered_parts.append(f"[git]\n{accepted}")
        truncated = truncated or was_truncated

    for ranked_file in ranked:
        if budget.remaining <= 0:
            truncated = True
            break
        content = ranked_file.file.path.read_text(encoding="utf-8", errors="replace")
        header = f"[file:{ranked_file.file.relative_path}]\n"
        accepted, was_truncated = budget.take(header + content)
        if not accepted:
            truncated = True
            break
        rendered_parts.append(accepted)
        selected_files.append(
            {
                "path": ranked_file.file.relative_path,
                "size_bytes": ranked_file.file.size_bytes,
                "score": ranked_file.score,
                "reasons": list(ranked_file.reasons),
                "included_tokens": budget.estimate_tokens(accepted),
            }
        )
        truncated = truncated or was_truncated

    context = "\n\n".join(rendered_parts)
    return ContextPacket(
        schema_version=1,
        task=task,
        workspace=str(guard.root),
        files=selected_files,
        symbols=[],
        definitions=[],
        references=[],
        git_changes=git_context.to_dict(),
        instructions=instructions,
        context=context,
        token_estimate=budget.estimate_tokens(context),
        token_budget=token_budget,
        truncated=truncated,
    )
