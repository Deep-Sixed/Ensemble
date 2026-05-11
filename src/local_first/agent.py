from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from local_first.config import LocalFirstConfig
from local_first.model import build_chat_model
from local_first.quality import inspect_response
from local_first.skills import inject_skill_cards


SYSTEM_PROMPT = """You are Local-First, a lean local AI development substrate.
You help inspect local profiles, MCP config, skills, and selected repositories.
In v1, you are not a replacement agent framework: writes and shell execution are
out of scope unless explicitly enabled by the operator. Prefer concise answers,
cite file paths when context is provided, and propose patches instead of editing.
"""


def ask(config: LocalFirstConfig, prompt: str, context: str | None = None) -> str:
    model = build_chat_model(config)
    skills = inject_skill_cards(prompt)
    parts = []
    if skills:
        parts.append(skills)
    if context is not None:
        parts.append(f"Context:\n{context}")
    parts.append(f"Question:\n{prompt}")
    content = "\n\n".join(parts)
    response = model.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
    )
    text = str(response.content)
    findings = inspect_response(text)
    if findings:
        notes = "\n".join(f"- {finding.code}: {finding.message}" for finding in findings)
        return f"{text}\n\n[Local-First quality monitor]\n{notes}".strip()
    return text
