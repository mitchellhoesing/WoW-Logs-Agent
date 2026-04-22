# CLAUDE.md — WoWLogsAgent

## Role

You are a **senior software engineer** working on WoWLogsAgent. Favor clarity, small well-named classes, strong typing, and testable pure code. Push back on scope creep and propose the simplest design that solves the stated problem. Never commit secrets. Never introduce a dependency without justification.

---

## 1. Project overview

WoWLogsAgent is a Python CLI that compares two (or more) World of Warcraft combat log reports pulled from WarcraftLogs.com and uses an LLM to produce prioritized, human-readable guidance for improving DPS. The target user is a raider who has a "good" and a "worse" log of the same encounter and wants to know — in plain language — what they did differently and what to change next pull.

The product hypothesis: most players can't read a combat log, but they *can* act on a ranked list of specific behavioral differences. Diffing two logs (rather than scoring one absolutely) produces sharper, more actionable advice because it anchors the LLM to the player's own baseline.

---

## 2. Pipeline (primary mental model)

Four stages. Each stage has clear inputs and outputs; stage boundaries are layer boundaries in the code.

1. **Fetch** — report IDs → raw WarcraftLogs v2 GraphQL responses (cached on disk).
2. **Normalize & combine** — raw responses → canonical domain entities (`CombatLog`, `Fight`, `Actor`, `AbilityUsage`) → a `PerformanceDelta` between two logs → a diff-framed LLM context payload.
3. **Analyze** — context payload → structured LLM response (the `ImprovementAnalyzer` calls the `LLMClient` port).
4. **Report** — LLM response → markdown guidelines written to stdout or a file.

Stages 2–3 depend only on domain ports; stages 1 and 4 live behind adapters.

---

## 3. External systems

- **WarcraftLogs v2 GraphQL** — `https://www.warcraftlogs.com/api/v2/client`. OAuth2 client-credentials flow (`https://www.warcraftlogs.com/oauth/token`). Rate-limited per client; cache aggressively during development.
- **LLM provider** — Anthropic is the default (`claude-opus-4-6` for deep analysis, `claude-sonnet-4-6` for cheaper iteration). Access is mediated by the `LLMClient` protocol so OpenAI or local providers can plug in without touching the domain.

---

## 4. Domain glossary

Use these terms consistently in code, prompts, and documentation.

- **report** — a WarcraftLogs upload (one raid night, one report code).
- **fight** — a single pull of an encounter within a report (has start/end, players, events).
- **encounter** — the boss/event being fought (e.g. Fyrakk). Identified by an encounter ID.
- **actor** — a participant in a fight: player, pet, or NPC. Carries class + spec for players.
- **ability** — a spell or action (identified by ability ID).
- **event** — a single combat-log line (cast, damage, heal, buff apply/remove, death).
- **parse** — a WCL percentile ranking of a player's performance on an encounter.
- **iLvl** — item level; proxy for gear.
- **specID** — WCL/WoW spec identifier (class + specialization).

---

## 5. Architecture — object-oriented, layered (hexagonal)

The project is organized around **objects and their responsibilities**, not around procedural pipeline stages. Layers flow inward: `cli → application → services → domain`. `gateways`, `infrastructure`, and `presentation` sit on the edges as plug-in implementations of domain-owned interfaces (ports). This keeps the domain pure, makes swaps (LLM provider, WCL transport, cache) local, and keeps tests tight.

```
WoWLogsAgent/
├── .github/workflows/ci.yml
├── .gitignore
├── .env.example
├── .python-version
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── LICENSE
├── Makefile
├── src/
│   └── wowlogs_agent/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py                          # Typer app; constructs + wires the AppContainer
│       │
│       ├── domain/                         # Pure: entities, value objects, domain services.
│       │   │                                 # No I/O. No framework imports.
│       │   ├── entities/
│       │   │   ├── combat_log.py           # class CombatLog  (aggregate root)
│       │   │   ├── fight.py                # class Fight      (duration, phases, events)
│       │   │   ├── actor.py                # class Actor      (class/spec, role)
│       │   │   └── ability_usage.py        # class AbilityUsage
│       │   ├── value_objects/
│       │   │   ├── dps.py                  # class DPS        (immutable, comparable)
│       │   │   ├── uptime.py               # class Uptime
│       │   │   └── time_window.py          # class TimeWindow
│       │   ├── performance/
│       │   │   ├── performance_profile.py  # class PerformanceProfile (derived from a Fight)
│       │   │   └── performance_delta.py    # class PerformanceDelta   (A vs. B)
│       │   └── ports/                      # Abstract interfaces the domain depends on.
│       │       ├── combat_log_repository.py    # class CombatLogRepository(ABC)
│       │       ├── llm_client.py               # class LLMClient(Protocol)
│       │       ├── prompt_template.py          # class PromptTemplate(ABC)
│       │       ├── run_recorder.py             # class RunRecorder(ABC)
│       │       └── report_renderer.py          # class ReportRenderer(ABC)
│       │
│       ├── services/                       # Domain services: behavior that doesn't belong
│       │   │                                 # to a single entity. Still pure.
│       │   ├── log_comparator.py           # class LogComparator          → PerformanceDelta
│       │   ├── context_builder.py          # class AnalysisContextBuilder → prompt payload
│       │   └── improvement_analyzer.py     # class ImprovementAnalyzer    → uses LLMClient
│       │
│       ├── application/                    # Use cases / orchestrators.
│       │   │                                 # Depend on domain ports, not concretes.
│       │   ├── use_cases/
│       │   │   └── compare_logs.py         # class CompareLogsUseCase.execute(report_a, report_b)
│       │   └── container.py                # class AppContainer (DI wiring)
│       │
│       ├── gateways/                       # Adapters implementing domain ports against the outside world.
│       │   ├── warcraft_logs/
│       │   │   ├── graphql_combat_log_repository.py  # class GraphQLCombatLogRepository
│       │   │   ├── oauth_token_provider.py           # class OAuthTokenProvider
│       │   │   ├── graphql_client.py                 # class WarcraftLogsGraphQLClient (httpx)
│       │   │   └── queries.py                        # GraphQL query constants
│       │   └── llm/
│       │       ├── anthropic_llm_client.py           # class AnthropicLLMClient(LLMClient)
│       │       └── openai_llm_client.py              # class OpenAILLMClient(LLMClient)   (stub)
│       │
│       ├── infrastructure/                 # Cross-cutting tech: config, persistence, logging.
│       │   ├── config.py                   # class Settings(BaseSettings)
│       │   ├── logging.py                  # configure_logging()
│       │   ├── cache/
│       │   │   └── filesystem_response_cache.py      # class FilesystemResponseCache
│       │   ├── runs/
│       │   │   └── filesystem_run_recorder.py        # class FilesystemRunRecorder(RunRecorder)
│       │   └── prompts/
│       │       └── file_prompt_template.py           # class FilePromptTemplate(PromptTemplate)
│       │
│       └── presentation/                   # Output adapters.
│           └── markdown_report_renderer.py # class MarkdownReportRenderer(ReportRenderer)
│
├── prompts/
│   └── compare_v1.md                       # versioned prompt templates
├── tests/
│   ├── conftest.py
│   ├── domain/                             # pure unit tests, no mocks
│   ├── services/                           # unit tests with fake ports
│   ├── application/                        # use-case tests with in-memory fakes
│   ├── gateways/                           # integration tests against recorded fixtures
│   ├── fixtures/                           # saved WCL GraphQL responses
│   └── snapshots/                          # built-context snapshots
├── runs/                                   # gitignored: per-invocation artifacts
└── .cache/                                 # gitignored: WCL response cache
```

### Design principles enforced by this layout

- **Dependency inversion.** `domain/` and `services/` import only from within themselves. Concretes in `gateways/`, `infrastructure/`, and `presentation/` implement abstract ports owned by the domain. The CLI and `AppContainer` are the only places that know about concrete implementations.
- **Rich domain model.** `Fight`, `CombatLog`, `PerformanceProfile`, `PerformanceDelta` have behavior (e.g. `fight.ability_uptime(ability_id)`, `profile.delta_against(other)`), not just data fields.
- **Value objects are immutable.** `DPS`, `Uptime`, `TimeWindow` are frozen dataclasses with equality and comparison.
- **Ports are tiny and single-purpose.** `CombatLogRepository.fetch(report_id) -> CombatLog`, `LLMClient.complete(messages, model) -> Response`. Easy to fake in tests.
- **Use cases are the only public surface the CLI calls.** `CompareLogsUseCase.execute(...)` is the entry point; swapping the CLI for a future web layer touches nothing below `application/`.
- **Testability.** `domain/` and `services/` tests need zero mocks. Gateway tests replay recorded fixtures. Use cases are tested with in-memory fake ports.

---

## 6. Stack & tooling

Baked into `pyproject.toml`:

- **Build:** `hatchling` (PEP 621 metadata).
- **Runtime deps:** `httpx`, `pydantic>=2`, `pydantic-settings`, `typer`, `structlog`, `anthropic`.
- **Dev deps:** `pytest`, `pytest-asyncio`, `pytest-snapshot`, `ruff`, `mypy`, `pre-commit`.
- **Lint + format:** `ruff` (replaces black/isort/flake8).
- **Typing:** `mypy --strict` on `src/`.
- **Pre-commit hooks:** ruff + mypy + a fast pytest subset.
- **CLI entry point:** `[project.scripts] wowlogs-agent = "wowlogs_agent.cli:app"`.

---

## 7. Config & secrets

`.env` keys:

- `WCL_CLIENT_ID`
- `WCL_CLIENT_SECRET`
- `ANTHROPIC_API_KEY`
- `WOWLOGS_LLM_MODEL` (optional; defaults to `claude-opus-4-6`)

`.env` is gitignored. `.env.example` is committed with placeholder values. Configuration is loaded via `pydantic-settings` in `infrastructure/config.py`. **Never** log secret values.

---

## 8. Working agreements

- `domain/` and `services/` are **pure and deterministic** — the same inputs produce the same prompt bytes, so runs are reproducible and diffable.
- Every LLM call persists prompt + response + metadata (model, prompt version, token counts, wall time) to `runs/<ISO-timestamp>/` via `RunRecorder`.
- Prompts live in `prompts/` and are **versioned by filename** (`compare_v1.md`, `compare_v2.md`). Bump the version for any semantic change; never edit a shipped prompt in place.
- Raw WCL responses are cached under `.cache/wcl/<reportId>/<query-hash>.json` so development doesn't re-hit the API.
- Tests: pure unit tests for `domain/` and `services/`; use-case tests with in-memory fake ports; gateway integration tests against recorded fixtures; snapshot tests for built contexts.
- Small modules, single-purpose classes, full type annotations. No broad `except Exception`. No `Any` without a comment explaining why.

---

## 9. Getting started (placeholder until code lands)

```bash
cp .env.example .env          # then fill in secrets
make install                  # pip install -e '.[dev]' + pre-commit install
make test
wowlogs-agent compare <reportIdA> <reportIdB>
```

# SYSTEM ARCHITECTURE & STANDARDS

## 1. Modular Design (OOP & SOLID)
Follow strict Object-Oriented and SOLID principles. Code must be decoupled, maintainable, and type-safe.

* **Single Responsibility (SRP):** Each class and function must have one, and only one, reason to change. Decompose monolithic logic into specialized modules.
* **Open/Closed (OCP):** Software entities should be open for extension but closed for modification. Favor composition over inheritance.
* **Liskov Substitution (LSP):** Subtypes must be entirely substitutable for their base types without breaking functionality.
* **Interface Segregation (ISP):** Prefer many small, specific interfaces over a single general-purpose interface.
* **Dependency Inversion (DIP):** High-level logic must depend on abstractions, not concrete implementations. Use Dependency Injection to provide external services.

### Implementation Constraints:
* **Type Safety:** All function signatures must use explicit Python type hints.
* **Immutability:** Use `@dataclass(frozen=True)` for data structures to prevent side effects.
* **State Management:** Avoid global variables. Encapsulate state within appropriate class scopes.

## 2. Testing Protocol (TDD)
Adopt a "Test-First" workflow. Functional code is incomplete without verified test coverage.

* **Framework:** Use `pytest`. Tests must inherit from `pytest.TestCase`.
* **Workflow:** 1. Write a failing test in the `tests/` directory. 
    2. Implement the minimum code required to satisfy the test. 
    3. Refactor while maintaining green tests.
* **Isolation:** Mock all external I/O, network requests, and API calls using `pytest-mock`. Tests must be deterministic and run offline.
* **Organization:** Mirror the source directory structure within `tests/`. Use the `test_<module>.py` naming convention.

## 3. Security & Integrity
Security is a primary constraint, not an afterthought.

* **Secrets:** Never hardcode credentials. Use environment variables and `.env` files. Ensure `.env` is in `.gitignore`.
* **Input Sanitization:** Treat all external data (User input, API responses, File reads) as untrusted. Validate types and bounds before processing.
* **Safe Serialization:** Avoid `pickle`. Use `json` or `yaml.safe_load` for data persistence.
* **Least Privilege:** Ensure components only have access to the data and permissions required for their specific task.
* **Error Handling:** Use explicit exception handling. Log detailed errors internally, but provide generic, safe messages to end-users to avoid info-leaks.

