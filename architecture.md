# WoWLogsAgent — Architecture

Map of the codebase as it stands. `CLAUDE.md` describes the *intended* design
and working agreements; this document describes what is actually implemented.

## 1. Layers

Hexagonal (ports-and-adapters). Dependencies point inward. The domain has no
I/O and no framework imports.

```
cli.py ──▶ application ──▶ services ──▶ domain
                │               │           ▲
                ▼               ▼           │
          gateways ◀────────────────────────┘
          infrastructure
          presentation
```

Only `cli.py` and `application/container.py` (`AppContainer`) know about
concrete gateway/infrastructure/presentation classes. Everything else talks
to domain-owned ports.

## 2. Domain (`src/wowlogs_agent/domain/`)

Pure entities, value objects, and abstract ports. No network, no disk, no
pydantic settings.

### Entities (`domain/entities/`)
- `CombatLog` — aggregate root; a single WarcraftLogs report with its fights.
- `Fight` — one pull of an encounter. Carries actors, ability usages, damage.
- `Actor` — participant in a fight (class, spec, role, item level).
- `AbilityUsage` — per-actor per-ability summary: casts, hits, damage, uptime.

### Value objects (`domain/value_objects/`)
- `DPS` — frozen, comparable; has `delta`, `pct_change_from`.
- `Uptime` — fraction/percent of a fight an effect was active.
- `TimeWindow` — `[start_ms, end_ms]`.

### Performance (`domain/performance/`)
- `PerformanceProfile` — per-actor summary derived from a Fight.
- `PerformanceDelta` — diff between two profiles. Always normalized so
  `delta.higher.dps >= delta.lower.dps`; ability-level diffs land in
  `delta.ability_deltas` sorted by absolute DPS-contribution impact.

### Ports (`domain/ports/`)
- `CombatLogRepository.fetch(report_id) -> CombatLog`
- `LLMClient.complete(messages, model, …) -> LLMResponse`
- `PromptTemplate.render(variables) -> str` (+ `version`)
- `RunRecorder.record(RunRecord) -> str`
- `ReportRenderer.render(delta, llm_analysis) -> str`

## 3. Services (`src/wowlogs_agent/services/`)

Domain services — stateless, deterministic, no I/O beyond what a port gives them.

- `LogComparator` — validates that two `CombatLog`s describe the same encounter
  and the same character's class/spec, then produces a `PerformanceDelta`.
  Requires an explicit `fight_id` per log; never auto-selects.
- `AnalysisContextBuilder` — serializes a `PerformanceDelta` to a deterministic
  JSON payload. Same delta → byte-identical JSON (sorted keys, fixed rounding)
  so runs are reproducible. Emits `higher_dps_run`/`lower_dps_run` sides.
- `ImprovementAnalyzer` — renders the context through a `PromptTemplate`, calls
  the `LLMClient`, and persists the exchange via `RunRecorder`.

## 4. Application (`src/wowlogs_agent/application/`)

- `use_cases/compare_logs.py` — `CompareLogsUseCase.execute(request)` is the
  only public entry point. `CompareLogsRequest` carries `report_id_a/b`,
  `fight_id_a/b`, `character_a`, optional `character_b`.
- `container.py` — `AppContainer` composes concretes to ports. `from_env()`
  loads `Settings` and defaults to the `compare_v2` prompt.

## 5. Gateways (`src/wowlogs_agent/gateways/`)

### WarcraftLogs (`gateways/warcraft_logs/`)
- `OAuthTokenProvider` — client-credentials flow against
  `https://www.warcraftlogs.com/oauth/token`. Caches the token until expiry.
- `WarcraftLogsGraphQLClient` — httpx-based transport against the v2 GraphQL
  endpoint. Wraps every request in a `FilesystemResponseCache` keyed by
  report + query hash.
- `GraphQLCombatLogRepository` — implements `CombatLogRepository` by issuing
  the queries in `queries.py` and mapping the response into domain entities.

### LLM (`gateways/llm/`)
- `AnthropicLLMClient` — concrete `LLMClient` using the `anthropic` SDK.
- `openai_llm_client.py` — placeholder stub kept to prove the port is generic.

## 6. Infrastructure (`src/wowlogs_agent/infrastructure/`)

- `config.py` — `Settings` via `pydantic-settings`. Loads `.env`, exposes
  `wcl_client_id`, `wcl_client_secret_value`, `anthropic_api_key_value`,
  `llm_model`, paths for `cache_dir`, `runs_dir`, `prompts_dir`.
- `logging.py` — structlog bootstrap; `configure_logging(level)` is called
  from the CLI.
- `cache/filesystem_response_cache.py` — JSON cache under `.cache/wcl/`.
- `runs/filesystem_run_recorder.py` — writes `messages.json`, `response.json`,
  `response.txt`, `metadata.json` under `runs/<ISO-timestamp>/`.
- `prompts/file_prompt_template.py` — loads versioned `*.md` templates from
  `prompts/` using `string.Template` substitution.

## 7. Presentation (`src/wowlogs_agent/presentation/`)

- `MarkdownReportRenderer` — builds the summary table (Higher-DPS run,
  Lower-DPS run, Δ), the top-10 ability deltas, and appends the LLM coaching.

## 8. Prompts (`prompts/`)

- `compare_v1.md` — original prompt. Kept for provenance; its JSON schema
  used `better`/`worse` field names and is no longer emitted.
- `compare_v2.md` — current default. Speaks in `higher_dps_run`/`lower_dps_run`
  and matches the `AnalysisContextBuilder` output. **Never edit a shipped
  prompt in place** — bump the version for any semantic change.

## 9. Data flow (happy path)

1. `cli.compare` parses `<reportId>?fight=<N>` args and instantiates
   `AppContainer.from_env(prompt_name="compare_v2")`.
2. `CompareLogsUseCase.execute` calls
   `GraphQLCombatLogRepository.fetch` twice (cache-backed).
3. `LogComparator.compare` validates matching encounter / class / spec and
   returns a `PerformanceDelta`.
4. `ImprovementAnalyzer.analyze` builds the context JSON, renders the prompt,
   calls `AnthropicLLMClient`, and writes `runs/<timestamp>/…`.
5. `MarkdownReportRenderer.render` stitches the delta table and the LLM
   response into a single markdown document, returned to the CLI for stdout
   or `--output`.

## 10. Testing

- `tests/domain` and `tests/services` run without mocks against in-memory
  fixtures in `tests/conftest.py` (`higher_log`, `lower_log`).
- `tests/application` exercises `CompareLogsUseCase` against fake ports.
- `tests/gateways` replays recorded WCL fixtures.
- `tests/test_cli.py` invokes Typer with a stubbed `AppContainer`.
