from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeWindow:
    """Half-open [start_ms, end_ms) interval measured in milliseconds from fight start."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must be >= 0")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be > start_ms")

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0

    def contains(self, timestamp_ms: int) -> bool:
        return self.start_ms <= timestamp_ms < self.end_ms

    def overlap(self, other: TimeWindow) -> int:
        lo = max(self.start_ms, other.start_ms)
        hi = min(self.end_ms, other.end_ms)
        return max(0, hi - lo)
