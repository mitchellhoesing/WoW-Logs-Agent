from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActorRole(StrEnum):
    TANK = "tank"
    HEALER = "healer"
    DPS = "dps"
    PET = "pet"
    NPC = "npc"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Actor:
    """A participant in a fight. Players carry class + spec; NPCs/pets do not."""

    id: int
    name: str
    role: ActorRole
    class_name: str | None = None
    spec_name: str | None = None
    item_level: float | None = None

    @property
    def is_player(self) -> bool:
        return self.role in (ActorRole.TANK, ActorRole.HEALER, ActorRole.DPS)

    @property
    def class_spec(self) -> str:
        if self.class_name and self.spec_name:
            return f"{self.spec_name} {self.class_name}"
        return self.class_name or "Unknown"
