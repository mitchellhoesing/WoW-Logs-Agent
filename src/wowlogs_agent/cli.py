from __future__ import annotations

import re
import sys
from pathlib import Path

import typer

from wowlogs_agent.application.container import AppContainer
from wowlogs_agent.application.use_cases import CompareLogsRequest
from wowlogs_agent.infrastructure.logging import configure_logging


def _ensure_utf8_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 so reports containing non-ASCII
    characters (Δ, em-dashes, spell names) render on Windows consoles that
    default to cp1252.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


_REPORT_FIGHT_RE = re.compile(
    r"^(?P<report>[A-Za-z0-9]+)[?#]fight=(?P<fight>\d+)$"
)


def _parse_report_arg(value: str) -> tuple[str, int]:
    """Split `<reportId>?fight=<N>` (or `#fight=<N>`) into (report_id, fight_id).

    Requires an explicit fight id — auto-selecting a fight silently changes
    what's being compared relative to the WCL URL the user copied.
    """
    match = _REPORT_FIGHT_RE.match(value.strip())
    if not match:
        raise typer.BadParameter(
            f"Expected '<reportId>?fight=<N>' (e.g. '98cQLtPqZGfWxNaX?fight=12'); "
            f"got {value!r}"
        )
    return match.group("report"), int(match.group("fight"))


app = typer.Typer(
    help="WoWLogsAgent — diff two WarcraftLogs reports and get DPS coaching from an LLM.",
    no_args_is_help=True,
)


@app.command()
def compare(
    character_a_log: str = typer.Option(
        ...,
        "--character-a-log",
        help="First run as '<reportId>?fight=<N>' (e.g. 'MYc79B2PL1tQdypA?fight=30').",
    ),
    character_b_log: str = typer.Option(
        ...,
        "--character-b-log",
        help="Second run as '<reportId>?fight=<N>' (e.g. '98cQLtPqZGfWxNaX?fight=36').",
    ),
    character_a: str = typer.Option(
        ...,
        "--character-a",
        "-c",
        help="Player character name in --character-a-log.",
    ),
    character_b: str | None = typer.Option(
        None,
        "--character-b",
        "-C",
        help="Player character name in --character-b-log. Defaults to --character-a.",
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the report to this file instead of stdout."
    ),
    prompt: str = typer.Option("compare_v3", "--prompt", help="Prompt template name."),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level."),
) -> None:
    """Compare two reports for one character and print actionable DPS coaching.

    The two runs are labelled by DPS, not by argument order: whichever run has
    higher DPS becomes the reference, and coaching focuses on lifting the
    lower-DPS run toward it.
    """

    _ensure_utf8_stdout()
    configure_logging(log_level)

    report_id_a, fight_id_a = _parse_report_arg(character_a_log)
    report_id_b, fight_id_b = _parse_report_arg(character_b_log)

    container = AppContainer.from_env(prompt_name=prompt)
    response = container.compare_logs.execute(
        CompareLogsRequest(
            report_id_a=report_id_a,
            report_id_b=report_id_b,
            fight_id_a=fight_id_a,
            fight_id_b=fight_id_b,
            character_a=character_a,
            character_b=character_b,
        )
    )

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(response.rendered_report, encoding="utf-8")
        typer.echo(f"Wrote report to {output} (model={response.model}, prompt={response.prompt_version})")
    else:
        typer.echo(response.rendered_report)


if __name__ == "__main__":
    app()
