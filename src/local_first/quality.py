from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityFinding:
    code: str
    message: str


def inspect_response(text: str, previous_tool_sequence: list[str] | None = None) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    stripped = text.strip()

    if not stripped:
        findings.append(QualityFinding("empty_reply", "Model returned an empty response."))

    if "fake_tool" in stripped.lower() or "<tool_call>" in stripped.lower():
        findings.append(
            QualityFinding("possible_fake_tool", "Response appears to include an unparsed tool call.")
        )

    if previous_tool_sequence and len(previous_tool_sequence) >= 6:
        tail = previous_tool_sequence[-6:]
        if tail[:3] == tail[3:]:
            findings.append(
                QualityFinding("repeated_tool_loop", "Tool sequence repeated twice.")
            )

    return findings


def needs_repair(text: str) -> bool:
    return any(finding.code in {"empty_reply", "possible_fake_tool"} for finding in inspect_response(text))
