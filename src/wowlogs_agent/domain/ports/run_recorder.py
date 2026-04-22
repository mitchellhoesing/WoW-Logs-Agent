from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from wowlogs_agent.domain.ports.llm_client import LLMMessage, LLMResponse


@dataclass(frozen=True)
class RunRecord:
    prompt_version: str
    model: str
    messages: Sequence[LLMMessage]
    response: LLMResponse
    wall_time_seconds: float
    metadata: dict[str, str]


class RunRecorder(ABC):
    """Port: persists a RunRecord to durable storage for later inspection."""

    @abstractmethod
    def record(self, run: RunRecord) -> str:
        """Persist the run and return an opaque locator (e.g. directory path)."""
