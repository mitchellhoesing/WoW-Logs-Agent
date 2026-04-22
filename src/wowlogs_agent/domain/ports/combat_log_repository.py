from __future__ import annotations

from abc import ABC, abstractmethod

from wowlogs_agent.domain.entities import CombatLog


class CombatLogRepository(ABC):
    """Port: fetches a CombatLog by report id. Implementations handle transport + caching."""

    @abstractmethod
    def fetch(
        self,
        report_id: str,
        *,
        fight_id: int | None = None,
        character_name: str | None = None,
    ) -> CombatLog:
        """Return a CombatLog for `report_id`.

        Optional hints let implementations skip expensive per-fight and per-actor
        queries when the caller only needs one fight and one character:

        - `fight_id`: if provided, only that fight is materialized.
        - `character_name`: if provided, per-actor data (e.g. buff uptime) is
          fetched only for that actor.
        """
