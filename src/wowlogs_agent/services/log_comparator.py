from __future__ import annotations

from dataclasses import dataclass

from wowlogs_agent.domain.entities import Actor, CombatLog
from wowlogs_agent.domain.performance import PerformanceDelta, PerformanceProfile


class LogComparisonError(ValueError):
    """Raised when two logs cannot be meaningfully compared."""


@dataclass(frozen=True)
class LogComparator:
    """Given two CombatLogs, specific fights in each, and a target actor, produce
    a PerformanceDelta.

    Pure domain service. The caller must pin each comparison to an explicit
    fight id — auto-selection would pick a different pull than the user saw in
    the WCL URL and silently change what's being compared.
    """

    def compare(
        self,
        log_a: CombatLog,
        log_b: CombatLog,
        *,
        fight_id_a: int,
        fight_id_b: int,
        character_a: str,
        character_b: str | None = None,
    ) -> PerformanceDelta:
        name_a = character_a
        name_b = character_b if character_b is not None else character_a

        fight_a = log_a.fight_by_id(fight_id_a)
        fight_b = log_b.fight_by_id(fight_id_b)
        if fight_a is None:
            raise LogComparisonError(
                f"Fight {fight_id_a} not found in report {log_a.report_id}"
            )
        if fight_b is None:
            raise LogComparisonError(
                f"Fight {fight_id_b} not found in report {log_b.report_id}"
            )
        if fight_a.encounter_id != fight_b.encounter_id:
            raise LogComparisonError(
                f"Encounter mismatch: {log_a.report_id}/fight {fight_id_a} is "
                f"{fight_a.encounter_name!r}, {log_b.report_id}/fight {fight_id_b} "
                f"is {fight_b.encounter_name!r}. Cross-encounter comparisons are "
                "not meaningful."
            )

        actor_a = fight_a.actor_by_name(name_a)
        actor_b = fight_b.actor_by_name(name_b)
        if actor_a is None:
            raise LogComparisonError(
                f"Actor {name_a!r} not present in fight "
                f"{log_a.report_id}/{fight_a.id}"
            )
        if actor_b is None:
            raise LogComparisonError(
                f"Actor {name_b!r} not present in fight "
                f"{log_b.report_id}/{fight_b.id}"
            )

        self._require_compatible_specs(actor_a, actor_b)

        profile_a = PerformanceProfile.from_fight(fight_a, actor_a, log_a.report_id)
        profile_b = PerformanceProfile.from_fight(fight_b, actor_b, log_b.report_id)
        return PerformanceDelta.build(higher=profile_a, lower=profile_b)

    @staticmethod
    def _require_compatible_specs(actor_a: Actor, actor_b: Actor) -> None:
        """Cross-actor comparisons are only meaningful within the same class+spec.

        When both sides advertise a class (or spec) and they disagree, refuse.
        When one side is missing the data, skip the check — we can't prove a
        mismatch, and erroring would block same-character runs where the
        gateway didn't fill in spec_name.
        """
        if (
            actor_a.class_name
            and actor_b.class_name
            and actor_a.class_name != actor_b.class_name
        ):
            raise LogComparisonError(
                f"Class mismatch: {actor_a.name!r} is {actor_a.class_name}, "
                f"{actor_b.name!r} is {actor_b.class_name}. Cross-class "
                "comparisons produce noise, not coaching."
            )
        if (
            actor_a.spec_name
            and actor_b.spec_name
            and actor_a.spec_name != actor_b.spec_name
        ):
            raise LogComparisonError(
                f"Spec mismatch: {actor_a.name!r} is {actor_a.class_spec}, "
                f"{actor_b.name!r} is {actor_b.class_spec}. Cross-spec "
                "comparisons produce noise, not coaching."
            )

