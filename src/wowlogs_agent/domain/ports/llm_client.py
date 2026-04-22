from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class LLMMessage:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    raw: dict[str, object]


class LLMClient(Protocol):
    """Port: minimal chat-completion surface used by ImprovementAnalyzer."""

    def complete(
        self,
        messages: Sequence[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse: ...
