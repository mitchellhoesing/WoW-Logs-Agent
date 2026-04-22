from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CombatEvent:
    """A single cast event emitted by an actor during a fight.

    Timestamps are fight-relative milliseconds — same basis as Fight.window.
    Scoped to casts only; damage/death/buff events are derived elsewhere so
    this type stays narrow until a later milestone needs richer shapes.
    """

    timestamp_ms: int
    ability_id: int
    source_id: int
    target_id: int | None = None

    def __post_init__(self) -> None:
        if self.timestamp_ms < 0:
            raise ValueError("timestamp_ms must be >= 0")
        if self.ability_id <= 0:
            raise ValueError("ability_id must be > 0")
        if self.source_id <= 0:
            raise ValueError("source_id must be > 0")

    @property
    def offset_seconds(self) -> float:
        return self.timestamp_ms / 1000.0
