from __future__ import annotations

from dataclasses import dataclass, field

from wowlogs_agent.domain.entities.fight import Fight


@dataclass(frozen=True)
class CombatLog:
    """Aggregate root: one WarcraftLogs report, potentially containing many fights."""

    report_id: str
    title: str
    owner: str
    start_unix_ms: int
    zone_name: str
    fights: tuple[Fight, ...] = field(default_factory=tuple)

    def fight_by_id(self, fight_id: int) -> Fight | None:
        for fight in self.fights:
            if fight.id == fight_id:
                return fight
        return None

    def fights_for_encounter(self, encounter_id: int) -> tuple[Fight, ...]:
        return tuple(f for f in self.fights if f.encounter_id == encounter_id)

    def best_fight_for_encounter(self, encounter_id: int) -> Fight | None:
        """Return the longest kill for the encounter, or longest pull if no kill."""
        candidates = self.fights_for_encounter(encounter_id)
        if not candidates:
            return None
        kills = [f for f in candidates if f.kill]
        pool = kills or list(candidates)
        return max(pool, key=lambda f: f.duration_seconds)
