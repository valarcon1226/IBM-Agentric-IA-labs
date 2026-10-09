"""Shared data shapes between `app.agent` (real OpenAI-compatible client) and `app.fake_llm`
(the `LLM_FAKE=true` scripted stand-in) — DECISIONES-13 W6.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMTurn:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
