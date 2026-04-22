from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class DPS:
    """Damage-per-second as a non-negative float. Immutable and comparable."""

    value: float

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError(f"DPS cannot be negative: {self.value}")

    @classmethod
    def from_total(cls, total_damage: float, duration_seconds: float) -> DPS:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be > 0")
        return cls(total_damage / duration_seconds)

    def delta(self, other: DPS) -> float:
        """Return self - other. Positive => self outperforms other."""
        return self.value - other.value

    def pct_change_from(self, baseline: DPS) -> float:
        """Percent change relative to baseline; 0.0 if baseline is 0."""
        if baseline.value == 0:
            return 0.0
        return (self.value - baseline.value) / baseline.value

    def __str__(self) -> str:
        return f"{self.value:,.0f} dps"
