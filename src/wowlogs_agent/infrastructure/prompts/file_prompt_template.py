from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from string import Template

from wowlogs_agent.domain.ports.prompt_template import PromptTemplate


class FilePromptTemplate(PromptTemplate):
    """Loads a prompt from `prompts/<name>.md` and substitutes `$var` placeholders.

    Uses `string.Template` so unrelated braces in the body (GraphQL-like, JSON, etc.)
    do not collide with substitution.
    """

    def __init__(self, name: str, body: str) -> None:
        self._name = name
        self._template = Template(body)

    @classmethod
    def load(cls, prompts_dir: Path, name: str) -> FilePromptTemplate:
        path = prompts_dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return cls(name=name, body=path.read_text(encoding="utf-8"))

    @property
    def version(self) -> str:
        return self._name

    def render(self, variables: Mapping[str, str]) -> str:
        return self._template.safe_substitute(variables)
