from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from wowlogs_agent.domain.entities.ability_usage import AbilityUsage
from wowlogs_agent.domain.entities.actor import Actor
from wowlogs_agent.domain.value_objects import DPS, Timeline, TimeWindow, Uptime


@dataclass(frozen=True)
class Fight:
    """A single pull of an encounter. Aggregate of actors, abilities, and summary stats."""

    id: int
    encounter_id: int
    encounter_name: str
    window: TimeWindow
    kill: bool
    difficulty: int
    actors: tuple[Actor, ...] = field(default_factory=tuple)
    # actor_id -> tuple of AbilityUsage
    ability_usages: Mapping[int, tuple[AbilityUsage, ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    # actor_id -> total damage done in this fight
    damage_by_actor: Mapping[int, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    # actor_id -> per-actor timeline (casts + buff windows + DPS-over-time).
    # Only populated for the compared character; defaults to empty for others.
    timelines: Mapping[int, Timeline] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def duration_seconds(self) -> float:
        return self.window.duration_seconds

    def actor_by_name(self, name: str) -> Actor | None:
        lower = name.lower()
        for actor in self.actors:
            if actor.name.lower() == lower:
                return actor
        return None

    def actor_by_id(self, actor_id: int) -> Actor | None:
        for actor in self.actors:
            if actor.id == actor_id:
                return actor
        return None

    def dps_for(self, actor_id: int) -> DPS:
        total = self.damage_by_actor.get(actor_id, 0)
        return DPS.from_total(total, self.duration_seconds)

    def ability_usages_for(self, actor_id: int) -> tuple[AbilityUsage, ...]:
        return self.ability_usages.get(actor_id, ())

    def ability_uptime(self, actor_id: int, ability_id: int) -> Uptime:
        for usage in self.ability_usages_for(actor_id):
            if usage.ability_id == ability_id:
                return usage.uptime
        return Uptime(0.0)

    def timeline_for(self, actor_id: int) -> Timeline | None:
        return self.timelines.get(actor_id)
