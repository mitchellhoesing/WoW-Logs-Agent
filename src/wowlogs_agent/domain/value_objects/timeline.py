from __future__ import annotations

from dataclasses import dataclass, field

from wowlogs_agent.domain.value_objects.dps import DPS


@dataclass(frozen=True, order=True)
class CooldownCast:
    """A single ability cast placed on the fight timeline.

    "Cooldown" here is a looser term than the player-facing meaning: every cast
    is a cooldown-candidate. Filtering to "important" abilities is left to
    downstream consumers (they have the names + per-spec knowledge).
    """

    timestamp_ms: int
    ability_id: int
    ability_name: str

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be >= 0")
        if self.ability_id <= 0:
            raise ValueError("ability_id must be > 0")

    @property
    def offset_seconds(self) -> float:
        return self.timestamp_ms / 1000.0


@dataclass(frozen=True, order=True)
class BuffWindow:
    """A single activation window for a buff on the tracked actor.

    start_ms/end_ms are fight-relative. A buff that fell off and came back is
    represented as two separate windows.
    """

    start_ms: int
    end_ms: int
    ability_id: int
    ability_name: str

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be > start_ms")
        if self.ability_id <= 0:
            raise ValueError("ability_id must be > 0")

    @property
    def duration_seconds(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0


@dataclass(frozen=True, order=True)
class DpsBucket:
    """Pre-bucketed DPS over a fixed window in the fight.

    Produced from WCL's pre-aggregated `graph` endpoint; the gateway never
    computes buckets itself.
    """

    start_ms: int
    end_ms: int
    dps: DPS

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be > start_ms")

    @property
    def duration_seconds(self) -> float:
        return (self.end_ms - self.start_ms) / 1000.0


@dataclass(frozen=True)
class Timeline:
    """Time-sequential view of a single actor's fight.

    Holds three independently-sourced summaries: cast events (from events API),
    buff windows (parsed from the same Buffs table we already fetch), and
    DPS-over-time (from the pre-aggregated graph endpoint).
    """

    cooldown_casts: tuple[CooldownCast, ...] = field(default_factory=tuple)
    buff_windows: tuple[BuffWindow, ...] = field(default_factory=tuple)
    dps_buckets: tuple[DpsBucket, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not (self.cooldown_casts or self.buff_windows or self.dps_buckets)
