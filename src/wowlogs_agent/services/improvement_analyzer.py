from __future__ import annotations

import time
from dataclasses import dataclass

from wowlogs_agent.domain.performance import PerformanceDelta
from wowlogs_agent.domain.ports import (
    LLMClient,
    LLMMessage,
    PromptTemplate,
    RunRecord,
    RunRecorder,
)
from wowlogs_agent.services.context_builder import AnalysisContextBuilder


@dataclass(frozen=True)
class AnalysisResult:
    text: str
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int


SYSTEM_PROMPT = (
    "You are a World of Warcraft raid coach. You compare two combat-log runs by the same "
    "player on the same encounter and produce a prioritized, specific, and actionable list "
    "of behaviors the player should change to improve DPS. Anchor every recommendation in "
    "the numbers provided; do not invent data. Prefer short, imperative advice."
)


@dataclass(frozen=True)
class ImprovementAnalyzer:
    """Invokes the LLM against a rendered prompt and records the run."""

    llm: LLMClient
    prompt_template: PromptTemplate
    run_recorder: RunRecorder
    context_builder: AnalysisContextBuilder
    model: str
    max_tokens: int = 4096
    temperature: float = 0.2

    def analyze(self, delta: PerformanceDelta) -> AnalysisResult:
        context_json = self.context_builder.build_json(delta)
        user_prompt = self.prompt_template.render(
            {
                "context_json": context_json,
                "encounter": delta.higher.encounter_name,
                "higher_character": delta.higher.actor.name,
                "higher_class_spec": delta.higher.actor.class_spec,
                "lower_character": delta.lower.actor.name,
                "lower_class_spec": delta.lower.actor.class_spec,
            }
        )
        messages = (
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        )

        start = time.perf_counter()
        response = self.llm.complete(
            messages=messages,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        elapsed = time.perf_counter() - start

        self.run_recorder.record(
            RunRecord(
                prompt_version=self.prompt_template.version,
                model=self.model,
                messages=messages,
                response=response,
                wall_time_seconds=elapsed,
                metadata={
                    "encounter": delta.higher.encounter_name,
                    "higher_dps_character": delta.higher.actor.name,
                    "lower_dps_character": delta.lower.actor.name,
                    "higher_dps_report": delta.higher.report_id,
                    "lower_dps_report": delta.lower.report_id,
                },
            )
        )

        return AnalysisResult(
            text=response.text,
            model=response.model,
            prompt_version=self.prompt_template.version,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
