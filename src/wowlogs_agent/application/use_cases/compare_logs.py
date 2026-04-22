from __future__ import annotations

from dataclasses import dataclass

from wowlogs_agent.domain.performance import PerformanceDelta
from wowlogs_agent.domain.ports import CombatLogRepository, ReportRenderer
from wowlogs_agent.services import ImprovementAnalyzer, LogComparator


@dataclass(frozen=True)
class CompareLogsRequest:
    report_id_a: str
    report_id_b: str
    fight_id_a: int
    fight_id_b: int
    character_a: str
    character_b: str | None = None


@dataclass(frozen=True)
class CompareLogsResponse:
    delta: PerformanceDelta
    analysis_text: str
    rendered_report: str
    model: str
    prompt_version: str


@dataclass(frozen=True)
class CompareLogsUseCase:
    """Orchestrates the fetch → compare → analyze → render pipeline.

    Depends only on ports, keeping gateway swaps local to the container.
    """

    repository: CombatLogRepository
    comparator: LogComparator
    analyzer: ImprovementAnalyzer
    renderer: ReportRenderer

    def execute(self, request: CompareLogsRequest) -> CompareLogsResponse:
        name_b = request.character_b or request.character_a
        log_a = self.repository.fetch(
            request.report_id_a,
            fight_id=request.fight_id_a,
            character_name=request.character_a,
        )
        log_b = self.repository.fetch(
            request.report_id_b,
            fight_id=request.fight_id_b,
            character_name=name_b,
        )

        delta = self.comparator.compare(
            log_a,
            log_b,
            fight_id_a=request.fight_id_a,
            fight_id_b=request.fight_id_b,
            character_a=request.character_a,
            character_b=request.character_b,
        )
        analysis = self.analyzer.analyze(delta)
        rendered = self.renderer.render(delta, analysis.text)

        return CompareLogsResponse(
            delta=delta,
            analysis_text=analysis.text,
            rendered_report=rendered,
            model=analysis.model,
            prompt_version=analysis.prompt_version,
        )
