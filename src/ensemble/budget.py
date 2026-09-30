from __future__ import annotations

from dataclasses import dataclass


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Provider-neutral approximation. Deliberately avoids a tokenizer dependency.
    return max(1, (len(text) + 3) // 4)


@dataclass
class ContextBudget:
    limit: int
    used: int = 0

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("token budget must be positive")

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return estimate_tokens(text)

    def take(self, text: str) -> tuple[str, bool]:
        if not text or self.remaining <= 0:
            return "", bool(text)

        tokens = estimate_tokens(text)
        if tokens <= self.remaining:
            self.used += tokens
            return text, False

        max_chars = self.remaining * 4
        if max_chars <= 0:
            return "", True
        clipped = text[:max_chars]
        self.used = self.limit
        return clipped, True
