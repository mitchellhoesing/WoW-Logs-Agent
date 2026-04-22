from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from wowlogs_agent.domain.entities.ability_usage import AbilityUsage
from wowlogs_agent.domain.entities.actor import Actor
from wowlogs_agent.domain.entities.fight import Fight
from wowlogs_agent.domain.value_objects import DPS, Timeline

if TYPE_CHECKING:
    from wowlogs_agent.domain.performance.performance_delta import PerformanceDelta


@dataclass(frozen=True)
class PerformanceProfile:
    """Per-actor summary derived from a single Fight.

    Pure: constructed from a Fight + Actor with no I/O. Used as the unit of comparison
    in PerformanceDelta.
    """

    report_id: str
    fight_id: int
    encounter_name: str
    duration_seconds: float
    actor: Actor
    dps: DPS
    ability_usages: tuple[AbilityUsage, ...]
    timeline: Timeline | None = None

    @classmethod
    def from_fight(cls, fight: Fight, actor: Actor, report_id: str) -> PerformanceProfile:
        return cls(
            report_id=report_id,
            fight_id=fight.id,
            encounter_name=fight.encounter_name,
            duration_seconds=fight.duration_seconds,
            actor=actor,
            dps=fight.dps_for(actor.id),
            ability_usages=fight.ability_usages_for(actor.id),
            timeline=fight.timeline_for(actor.id),
        )

    def usage_for(self, ability_id: int) -> AbilityUsage | None:
        for u in self.ability_usages:
            if u.ability_id == ability_id:
                return u
        return None

    def delta_against(self, baseline: PerformanceProfile) -> PerformanceDelta:
        from wowlogs_agent.domain.performance.performance_delta import (
            PerformanceDelta as _PerformanceDelta,
        )

        return _PerformanceDelta.build(higher=self, lower=baseline)
