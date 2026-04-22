from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Uptime:
    """Fraction of fight time a buff/debuff/ability was active. Range [0, 1]."""

    fraction: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.fraction <= 1.0:
            raise ValueError(f"Uptime fraction must be in [0,1]: {self.fraction}")

    @classmethod
    def from_seconds(cls, active_seconds: float, total_seconds: float) -> Uptime:
        if total_seconds <= 0:
            raise ValueError("total_seconds must be > 0")
        return cls(max(0.0, min(1.0, active_seconds / total_seconds)))

    @property
    def percent(self) -> float:
        return self.fraction * 100.0

    def delta(self, other: Uptime) -> float:
        return self.fraction - other.fraction

    def __str__(self) -> str:
        return f"{self.percent:.1f}%"
