from __future__ import annotations

from dataclasses import dataclass

from wowlogs_agent.domain.value_objects import DPS, Uptime


@dataclass(frozen=True)
class AbilityUsage:
    """Aggregated usage of a single ability by a single actor over a single fight."""

    ability_id: int
    name: str
    casts: int
    hits: int
    total_damage: int
    active_seconds: float
    fight_duration_seconds: float

    def __post_init__(self) -> None:
        if self.casts < 0 or self.hits < 0 or self.total_damage < 0:
            raise ValueError("AbilityUsage counts must be non-negative")
        if self.fight_duration_seconds <= 0:
            raise ValueError("fight_duration_seconds must be > 0")
        if self.active_seconds < 0:
            raise ValueError("active_seconds must be >= 0")

    @property
    def dps_contribution(self) -> DPS:
        return DPS.from_total(self.total_damage, self.fight_duration_seconds)

    @property
    def uptime(self) -> Uptime:
        return Uptime.from_seconds(self.active_seconds, self.fight_duration_seconds)

    @property
    def damage_per_cast(self) -> float:
        return self.total_damage / self.casts if self.casts else 0.0
