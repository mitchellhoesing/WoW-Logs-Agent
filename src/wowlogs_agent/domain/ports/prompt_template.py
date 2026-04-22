from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping


class PromptTemplate(ABC):
    """Port: versioned prompt templates loaded from disk and rendered with variables."""

    @property
    @abstractmethod
    def version(self) -> str:
        """Identifier baked into run metadata (e.g. `compare_v1`)."""

    @abstractmethod
    def render(self, variables: Mapping[str, str]) -> str:
        """Return the rendered prompt body with `{var}` placeholders substituted."""
