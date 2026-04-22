from __future__ import annotations

from dataclasses import dataclass

from wowlogs_agent.domain.entities.ability_usage import AbilityUsage
from wowlogs_agent.domain.performance.performance_profile import PerformanceProfile


@dataclass(frozen=True)
class AbilityDelta:
    """Difference in a single ability's usage between two profiles.

    `higher` is from the higher-DPS run; `lower` is from the lower-DPS run.
    `None` on either side means the ability was absent in that log.
    """

    ability_id: int
    name: str
    higher: AbilityUsage | None
    lower: AbilityUsage | None

    @property
    def casts_delta(self) -> int:
        hi = self.higher.casts if self.higher else 0
        lo = self.lower.casts if self.lower else 0
        return hi - lo

    @property
    def damage_delta(self) -> int:
        hi = self.higher.total_damage if self.higher else 0
        lo = self.lower.total_damage if self.lower else 0
        return hi - lo

    @property
    def uptime_delta(self) -> float:
        hi = self.higher.uptime.fraction if self.higher else 0.0
        lo = self.lower.uptime.fraction if self.lower else 0.0
        return hi - lo

    @property
    def dps_contribution_delta(self) -> float:
        hi = self.higher.dps_contribution.value if self.higher else 0.0
        lo = self.lower.dps_contribution.value if self.lower else 0.0
        return hi - lo


@dataclass(frozen=True)
class PerformanceDelta:
    """Structured comparison of two PerformanceProfiles for the same actor and encounter.

    Sides are labelled by DPS: `higher` is the run with higher DPS, `lower` is the run
    with lower DPS. `build()` normalizes argument order so this invariant always holds.
    """

    higher: PerformanceProfile
    lower: PerformanceProfile
    dps_delta: float
    dps_pct_change: float
    duration_delta_seconds: float
    ability_deltas: tuple[AbilityDelta, ...]

    @classmethod
    def build(cls, higher: PerformanceProfile, lower: PerformanceProfile) -> PerformanceDelta:
        if higher.dps < lower.dps:
            higher, lower = lower, higher

        all_ids: set[int] = {u.ability_id for u in higher.ability_usages}
        all_ids.update(u.ability_id for u in lower.ability_usages)

        deltas: list[AbilityDelta] = []
        for ability_id in all_ids:
            hi = higher.usage_for(ability_id)
            lo = lower.usage_for(ability_id)
            name = (hi.name if hi else None) or (lo.name if lo else f"ability:{ability_id}")
            deltas.append(AbilityDelta(ability_id=ability_id, name=name, higher=hi, lower=lo))

        deltas.sort(key=lambda d: abs(d.dps_contribution_delta), reverse=True)

        return cls(
            higher=higher,
            lower=lower,
            dps_delta=higher.dps.delta(lower.dps),
            dps_pct_change=higher.dps.pct_change_from(lower.dps),
            duration_delta_seconds=higher.duration_seconds - lower.duration_seconds,
            ability_deltas=tuple(deltas),
        )

    def top_ability_deltas(self, n: int = 10) -> tuple[AbilityDelta, ...]:
        return self.ability_deltas[:n]
