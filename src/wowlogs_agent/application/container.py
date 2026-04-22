from __future__ import annotations

from functools import cached_property
from pathlib import Path

from wowlogs_agent.application.use_cases import CompareLogsUseCase
from wowlogs_agent.domain.ports import (
    CombatLogRepository,
    LLMClient,
    PromptTemplate,
    ReportRenderer,
    RunRecorder,
)
from wowlogs_agent.gateways.llm.anthropic_llm_client import AnthropicLLMClient
from wowlogs_agent.gateways.warcraft_logs.graphql_client import WarcraftLogsGraphQLClient
from wowlogs_agent.gateways.warcraft_logs.graphql_combat_log_repository import (
    GraphQLCombatLogRepository,
)
from wowlogs_agent.gateways.warcraft_logs.oauth_token_provider import OAuthTokenProvider
from wowlogs_agent.infrastructure.cache.filesystem_response_cache import FilesystemResponseCache
from wowlogs_agent.infrastructure.config import Settings
from wowlogs_agent.infrastructure.prompts.file_prompt_template import FilePromptTemplate
from wowlogs_agent.infrastructure.runs.filesystem_run_recorder import FilesystemRunRecorder
from wowlogs_agent.presentation.markdown_report_renderer import MarkdownReportRenderer
from wowlogs_agent.services import AnalysisContextBuilder, ImprovementAnalyzer, LogComparator


class AppContainer:
    """Composition root. Wires concretes to ports; only place that knows about them."""

    def __init__(self, settings: Settings, prompt_name: str = "compare_v2") -> None:
        self.settings = settings
        self.prompt_name = prompt_name

    @cached_property
    def response_cache(self) -> FilesystemResponseCache:
        return FilesystemResponseCache(self.settings.cache_dir / "wcl")

    @cached_property
    def token_provider(self) -> OAuthTokenProvider:
        return OAuthTokenProvider(
            client_id=self.settings.wcl_client_id,
            client_secret=self.settings.wcl_client_secret_value,
            token_url=self.settings.wcl_token_url,
        )

    @cached_property
    def graphql_client(self) -> WarcraftLogsGraphQLClient:
        return WarcraftLogsGraphQLClient(
            endpoint=self.settings.wcl_endpoint,
            token_provider=self.token_provider,
            cache=self.response_cache,
        )

    @cached_property
    def repository(self) -> CombatLogRepository:
        return GraphQLCombatLogRepository(client=self.graphql_client)

    @cached_property
    def llm_client(self) -> LLMClient:
        return AnthropicLLMClient(api_key=self.settings.anthropic_api_key_value)

    @cached_property
    def prompt_template(self) -> PromptTemplate:
        return FilePromptTemplate.load(self.settings.prompts_dir, self.prompt_name)

    @cached_property
    def run_recorder(self) -> RunRecorder:
        return FilesystemRunRecorder(self.settings.runs_dir)

    @cached_property
    def comparator(self) -> LogComparator:
        return LogComparator()

    @cached_property
    def context_builder(self) -> AnalysisContextBuilder:
        return AnalysisContextBuilder()

    @cached_property
    def analyzer(self) -> ImprovementAnalyzer:
        return ImprovementAnalyzer(
            llm=self.llm_client,
            prompt_template=self.prompt_template,
            run_recorder=self.run_recorder,
            context_builder=self.context_builder,
            model=self.settings.llm_model,
        )

    @cached_property
    def renderer(self) -> ReportRenderer:
        return MarkdownReportRenderer()

    @cached_property
    def compare_logs(self) -> CompareLogsUseCase:
        return CompareLogsUseCase(
            repository=self.repository,
            comparator=self.comparator,
            analyzer=self.analyzer,
            renderer=self.renderer,
        )

    @classmethod
    def from_env(cls, project_root: Path | None = None, prompt_name: str = "compare_v2") -> AppContainer:
        settings = Settings.load(project_root=project_root)
        return cls(settings=settings, prompt_name=prompt_name)
