from __future__ import annotations

from abc import ABC, abstractmethod

from wowlogs_agent.domain.performance import PerformanceDelta


class ReportRenderer(ABC):
    """Port: turns a delta + LLM analysis into a human-readable artifact."""

    @abstractmethod
    def render(self, delta: PerformanceDelta, llm_analysis: str) -> str:
        """Return the final formatted report as a single string."""
