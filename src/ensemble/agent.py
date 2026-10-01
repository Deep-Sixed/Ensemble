from __future__ import annotations

from ensemble.config import EnsembleConfig
from ensemble.llm import ChatClient
from ensemble.quality import inspect_response
from ensemble.skills import inject_skill_cards


SYSTEM_PROMPT = """You are Ensemble, a lean local AI development substrate.
You help inspect local profiles, MCP config, skills, and selected repositories.
This one-shot mode has no tools: propose patches as text instead of editing.
Prefer concise answers and cite file paths when context is provided.
"""


def ask(config: EnsembleConfig, prompt: str, context: str | None = None) -> str:
    """One-shot question without tools. Use `ensemble agent` for the coding harness."""
    skills = inject_skill_cards(prompt)
    parts = []
    if skills:
        parts.append(skills)
    if context is not None:
        parts.append(f"Context:\n{context}")
    parts.append(f"Question:\n{prompt}")
    turn = ChatClient(config).complete(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(parts)},
        ]
    )
    text = turn.content
    findings = inspect_response(text)
    if findings:
        notes = "\n".join(f"- {finding.code}: {finding.message}" for finding in findings)
        return f"{text}\n\n[Ensemble quality monitor]\n{notes}".strip()
    return text
