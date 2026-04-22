from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from wowlogs_agent import cli as cli_module
from wowlogs_agent.application.use_cases import CompareLogsRequest


@dataclass
class _FakeResponse:
    rendered_report: str = "# Report\nadvice"
    model: str = "claude-sonnet-4-6"
    prompt_version: str = "compare_v2"
    delta: Any = None
    analysis_text: str = "advice"


class _FakeUseCase:
    def __init__(self) -> None:
        self.calls: list[CompareLogsRequest] = []

    def execute(self, request: CompareLogsRequest) -> _FakeResponse:
        self.calls.append(request)
        return _FakeResponse()


class _FakeContainer:
    def __init__(self, prompt_name: str) -> None:
        self.prompt_name = prompt_name
        self.compare_logs = _FakeUseCase()


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_container(monkeypatch: pytest.MonkeyPatch) -> list[_FakeContainer]:
    created: list[_FakeContainer] = []

    def _from_env(prompt_name: str = "compare_v2", **_: Any) -> _FakeContainer:
        c = _FakeContainer(prompt_name=prompt_name)
        created.append(c)
        return c

    monkeypatch.setattr(cli_module.AppContainer, "from_env", staticmethod(_from_env))
    return created


def test_compare_writes_report_to_stdout(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA?fight=1",
            "--character-b-log",
            "BBB?fight=2",
            "--character-a",
            "Zug",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "# Report" in result.output
    assert "advice" in result.output

    request = fake_container[0].compare_logs.calls[0]
    assert request.report_id_a == "AAA"
    assert request.report_id_b == "BBB"
    assert request.fight_id_a == 1
    assert request.fight_id_b == 2
    assert request.character_a == "Zug"


def test_compare_accepts_hash_fight_separator(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA#fight=7",
            "--character-b-log",
            "BBB#fight=8",
            "--character-a",
            "Zug",
        ],
    )

    assert result.exit_code == 0, result.output
    request = fake_container[0].compare_logs.calls[0]
    assert request.fight_id_a == 7
    assert request.fight_id_b == 8


def test_compare_rejects_bare_report_id(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA",
            "--character-b-log",
            "BBB",
            "--character-a",
            "Zug",
        ],
    )
    assert result.exit_code != 0
    assert "fight=" in result.output


def test_compare_forwards_character_b(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA?fight=1",
            "--character-b-log",
            "BBB?fight=2",
            "--character-a",
            "PlayerA",
            "--character-b",
            "PlayerB",
        ],
    )

    assert result.exit_code == 0, result.output
    request = fake_container[0].compare_logs.calls[0]
    assert request.character_a == "PlayerA"
    assert request.character_b == "PlayerB"


def test_compare_defaults_character_b_to_none_when_not_given(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA?fight=1",
            "--character-b-log",
            "BBB?fight=2",
            "--character-a",
            "Zug",
        ],
    )
    assert result.exit_code == 0, result.output
    assert fake_container[0].compare_logs.calls[0].character_b is None


def test_compare_writes_to_output_file_when_specified(
    runner: CliRunner, fake_container: list[_FakeContainer], tmp_path: Path
) -> None:
    out = tmp_path / "nested" / "report.md"
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA?fight=1",
            "--character-b-log",
            "BBB?fight=2",
            "--character-a",
            "Zug",
            "--output",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert out.read_text(encoding="utf-8") == "# Report\nadvice"
    assert "Wrote report to" in result.output
    assert "# Report" not in result.output


def test_compare_passes_prompt_name_to_container(
    runner: CliRunner, fake_container: list[_FakeContainer]
) -> None:
    result = runner.invoke(
        cli_module.app,
        [
            "--character-a-log",
            "AAA?fight=1",
            "--character-b-log",
            "BBB?fight=2",
            "--character-a",
            "Zug",
            "--prompt",
            "compare_v3",
        ],
    )

    assert result.exit_code == 0, result.output
    assert fake_container[0].prompt_name == "compare_v3"


def test_missing_required_character_a_flag_fails(runner: CliRunner) -> None:
    result = runner.invoke(
        cli_module.app,
        ["--character-a-log", "AAA?fight=1", "--character-b-log", "BBB?fight=2"],
    )
    assert result.exit_code != 0
    assert "character" in result.output.lower()
