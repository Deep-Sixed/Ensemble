from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from local_first.config import LocalFirstConfig
from local_first.model import build_chat_model


SYSTEM_PROMPT = """You are Local-First, a local AI control layer.
You help inspect selected repositories safely. In v1, writes and shell execution
are disabled unless explicitly enabled by the operator. Prefer concise answers,
cite file paths when context is provided, and propose patches instead of editing.
"""


def ask(config: LocalFirstConfig, prompt: str, context: str | None = None) -> str:
    model = build_chat_model(config)
    content = prompt if context is None else f"Context:\n{context}\n\nQuestion:\n{prompt}"
    response = model.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=content),
        ]
    )
    return str(response.content)
