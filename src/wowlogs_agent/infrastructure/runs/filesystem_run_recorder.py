from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from wowlogs_agent.domain.ports.run_recorder import RunRecord, RunRecorder


class FilesystemRunRecorder(RunRecorder):
    """Writes each LLM call to `runs/<ISO-timestamp>/` as separate files.

    Layout:
      runs/<timestamp>/
        messages.json    — full prompt history sent to the model
        response.txt     — plain-text response body
        response.json    — raw provider response dump
        metadata.json    — model, prompt version, tokens, wall time, extras
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def record(self, run: RunRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%I-%M%p")
        target = self._root / timestamp
        suffix = 2
        while target.exists():
            target = self._root / f"{timestamp}-{suffix}"
            suffix += 1
        target.mkdir(parents=True)

        (target / "messages.json").write_text(
            json.dumps(
                [{"role": m.role, "content": m.content} for m in run.messages],
                indent=2,
            ),
            encoding="utf-8",
        )
        (target / "response.txt").write_text(run.response.text, encoding="utf-8")
        (target / "response.json").write_text(
            json.dumps(run.response.raw, indent=2, default=str),
            encoding="utf-8",
        )
        (target / "metadata.json").write_text(
            json.dumps(
                {
                    "prompt_version": run.prompt_version,
                    "model": run.model,
                    "input_tokens": run.response.input_tokens,
                    "output_tokens": run.response.output_tokens,
                    "wall_time_seconds": run.wall_time_seconds,
                    "metadata": run.metadata,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return str(target)
