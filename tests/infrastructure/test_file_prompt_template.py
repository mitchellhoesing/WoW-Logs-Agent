from __future__ import annotations

from pathlib import Path

import pytest

from wowlogs_agent.infrastructure.prompts.file_prompt_template import FilePromptTemplate


def test_load_reads_named_prompt_from_directory(tmp_path: Path) -> None:
    (tmp_path / "greet.md").write_text("Hello $name", encoding="utf-8")

    tmpl = FilePromptTemplate.load(tmp_path, "greet")

    assert tmpl.version == "greet"
    assert tmpl.render({"name": "Zug"}) == "Hello Zug"


def test_load_raises_when_prompt_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        FilePromptTemplate.load(tmp_path, "nonexistent")


def test_render_leaves_unknown_placeholders_alone() -> None:
    tmpl = FilePromptTemplate(name="t", body="Hi $name, $unknown")
    assert tmpl.render({"name": "Zug"}) == "Hi Zug, $unknown"


def test_render_does_not_treat_braces_as_substitutions() -> None:
    tmpl = FilePromptTemplate(name="t", body='{"actor": "$name", "nested": {"k": 1}}')
    rendered = tmpl.render({"name": "Zug"})
    assert rendered == '{"actor": "Zug", "nested": {"k": 1}}'


def test_version_exposes_template_name() -> None:
    tmpl = FilePromptTemplate(name="compare_v3", body="x")
    assert tmpl.version == "compare_v3"
