from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from wowlogs_agent.application.use_cases import CompareLogsRequest, CompareLogsUseCase
from wowlogs_agent.domain.entities import CombatLog
from wowlogs_agent.domain.ports import (
    CombatLogRepository,
    LLMClient,
    LLMMessage,
    LLMResponse,
    PromptTemplate,
    RunRecord,
    RunRecorder,
)
from wowlogs_agent.presentation.markdown_report_renderer import MarkdownReportRenderer
from wowlogs_agent.services import AnalysisContextBuilder, ImprovementAnalyzer, LogComparator


class FakeRepo(CombatLogRepository):
    def __init__(self, logs: dict[str, CombatLog]) -> None:
        self._logs = logs

    def fetch(
        self,
        report_id: str,
        *,
        fight_id: int | None = None,
        character_name: str | None = None,
    ) -> CombatLog:
        return self._logs[report_id]


@dataclass
class FakeLLM(LLMClient):
    captured: list[Sequence[LLMMessage]]

    def complete(
        self,
        messages: Sequence[LLMMessage],
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        self.captured.append(tuple(messages))
        return LLMResponse(
            text="1. Cast Mortal Strike more.\n2. Maintain Bladestorm.",
            model=model,
            input_tokens=100,
            output_tokens=50,
            raw={"stub": True},
        )


class StaticPrompt(PromptTemplate):
    @property
    def version(self) -> str:
        return "test_v0"

    def render(self, variables: Mapping[str, str]) -> str:
        return f"CTX:{variables.get('context_json', '')[:40]}"


class NullRecorder(RunRecorder):
    def __init__(self) -> None:
        self.records: list[RunRecord] = []

    def record(self, run: RunRecord) -> str:
        self.records.append(run)
        return "memory://run"


class TestCompareLogsUseCase:
    def test_end_to_end_with_fakes(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        repo = FakeRepo({higher_log.report_id: higher_log, lower_log.report_id: lower_log})
        llm = FakeLLM(captured=[])
        recorder = NullRecorder()
        analyzer = ImprovementAnalyzer(
            llm=llm,
            prompt_template=StaticPrompt(),
            run_recorder=recorder,
            context_builder=AnalysisContextBuilder(),
            model="test-model",
        )
        use_case = CompareLogsUseCase(
            repository=repo,
            comparator=LogComparator(),
            analyzer=analyzer,
            renderer=MarkdownReportRenderer(),
        )

        response = use_case.execute(
            CompareLogsRequest(
                report_id_a=higher_log.report_id,
                report_id_b=lower_log.report_id,
                fight_id_a=higher_log.fights[0].id,
                fight_id_b=lower_log.fights[0].id,
                character_a="Zug",
            )
        )

        assert "Zug" in response.rendered_report
        assert "Fyrakk" in response.rendered_report
        assert "Mortal Strike" in response.rendered_report
        assert response.model == "test-model"
        assert response.prompt_version == "test_v0"
        assert len(recorder.records) == 1
        assert len(llm.captured) == 1
