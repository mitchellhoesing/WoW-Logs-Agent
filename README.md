This project serves as a passion project and Claude Code capabilities exploration.

# RaidMind: WoWLogsAgent

LLM-powered analyzer that compares two WarcraftLogs combat reports and produces a
prioritized, human-readable list of changes a player can make to improve their DPS.

The two runs are labelled by DPS, not by the order you pass them: whichever has
higher DPS becomes the reference, and coaching focuses on lifting the lower-DPS run
toward it.

See `CLAUDE.md` for architecture intent and working agreements, and
`architecture.md` for a map of what's in the codebase today.

## Requirements

- Python 3.11+
- A WarcraftLogs v2 API client (`WCL_CLIENT_ID` + `WCL_CLIENT_SECRET`)
- An Anthropic API key (`ANTHROPIC_API_KEY`)

## Setup

```bash
cp .env.example .env     # then fill in secrets — never commit .env
make install             # pip install -e '.[dev]' + pre-commit install
make test                # run the full pytest suite
```

## Running

The CLI takes two reports in `<reportId>?fight=<N>` form (copy the URL straight
from WarcraftLogs) and the character name to analyze.

```bash
wowlogs-agent compare \
    --character-a-log 'MYc79B2PL1tQdypA?fight=30' \
    --character-b-log '98cQLtPqZGfWxNaX?fight=36' \
    --character-a YourCharacter
```

Common flags:

- `--character-a-log <reportId>?fight=<N>` (required) — first run.
- `--character-b-log <reportId>?fight=<N>` (required) — second run.
- `--character-a <name>` (required) — character in `--character-a-log`.
- `--character-b <name>` — character in `--character-b-log`. Defaults to `--character-a`.
- `--output <path>` — write the markdown report to a file instead of stdout.
- `--prompt <name>` — prompt template to use (default `compare_v2`; see `prompts/`).
- `--log-level <level>` — `DEBUG`, `INFO`, `WARNING`, `ERROR`.

Alternatively, inside the project venv:

```bash
python scripts/run_env.py 'REPORT_A?fight=1' 'REPORT_B?fight=2' --character-a YourCharacter
```

## Output & artifacts

- The report is markdown with a summary table, top ability deltas, and LLM coaching.
- Every LLM call is persisted to `runs/<ISO-timestamp>/` (prompt, response, metadata).
- WarcraftLogs GraphQL responses are cached under `.cache/wcl/` so repeated runs
  don't re-hit the API.

Both directories are gitignored.

## Layout

- `src/wowlogs_agent/domain` — pure entities, value objects, ports.
- `src/wowlogs_agent/services` — domain services (comparator, context builder, analyzer).
- `src/wowlogs_agent/application` — use cases + DI container.
- `src/wowlogs_agent/gateways` — WarcraftLogs + LLM adapters.
- `src/wowlogs_agent/infrastructure` — config, logging, caches, run recording.
- `src/wowlogs_agent/presentation` — markdown rendering.
- `prompts/` — versioned prompt templates.
