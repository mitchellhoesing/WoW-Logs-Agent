from __future__ import annotations

import json
from pathlib import Path

from wowlogs_agent.domain.ports.llm_client import LLMMessage, LLMResponse
from wowlogs_agent.domain.ports.run_recorder import RunRecord
from wowlogs_agent.infrastructure.runs.filesystem_run_recorder import (
    FilesystemRunRecorder,
)


def _record() -> RunRecord:
    return RunRecord(
        prompt_version="compare_v1",
        model="claude-sonnet-4-6",
        messages=(
            LLMMessage(role="system", content="sys"),
            LLMMessage(role="user", content="hi"),
        ),
        response=LLMResponse(
            text="advice",
            model="claude-sonnet-4-6",
            input_tokens=10,
            output_tokens=20,
            raw={"id": "msg_1"},
        ),
        wall_time_seconds=1.25,
        metadata={"actor": "Zug"},
    )


def test_record_writes_all_artifacts(tmp_path: Path) -> None:
    recorder = FilesystemRunRecorder(tmp_path)

    locator = recorder.record(_record())

    target = Path(locator)
    assert target.parent == tmp_path
    assert (target / "messages.json").is_file()
    assert (target / "response.txt").is_file()
    assert (target / "response.json").is_file()
    assert (target / "metadata.json").is_file()


def test_response_text_is_written_verbatim(tmp_path: Path) -> None:
    recorder = FilesystemRunRecorder(tmp_path)
    target = Path(recorder.record(_record()))

    assert (target / "response.txt").read_text(encoding="utf-8") == "advice"


def test_messages_round_trip_as_json(tmp_path: Path) -> None:
    recorder = FilesystemRunRecorder(tmp_path)
    target = Path(recorder.record(_record()))

    data = json.loads((target / "messages.json").read_text(encoding="utf-8"))
    assert data == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]


def test_metadata_captures_tokens_model_and_extras(tmp_path: Path) -> None:
    recorder = FilesystemRunRecorder(tmp_path)
    target = Path(recorder.record(_record()))

    meta = json.loads((target / "metadata.json").read_text(encoding="utf-8"))
    assert meta["prompt_version"] == "compare_v1"
    assert meta["model"] == "claude-sonnet-4-6"
    assert meta["input_tokens"] == 10
    assert meta["output_tokens"] == 20
    assert meta["wall_time_seconds"] == 1.25
    assert meta["metadata"] == {"actor": "Zug"}


def test_each_record_gets_its_own_directory(tmp_path: Path) -> None:
    recorder = FilesystemRunRecorder(tmp_path)

    first = recorder.record(_record())
    second = recorder.record(_record())

    assert first != second
    assert Path(first).is_dir() and Path(second).is_dir()
