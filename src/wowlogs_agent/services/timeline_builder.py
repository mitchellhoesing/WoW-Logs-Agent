from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from wowlogs_agent.domain.entities import CombatEvent
from wowlogs_agent.domain.value_objects import BuffWindow, CooldownCast, DpsBucket, Timeline


@dataclass(frozen=True)
class TimelineBuilder:
    """Composes a Timeline from the three independent inputs the gateway collects.

    Pure and deterministic: same inputs produce identical output bytes.

    The gateway is responsible for converting absolute WCL timestamps to
    fight-relative milliseconds before calling in. This service just sorts,
    names, and packages.
    """

    def build(
        self,
        *,
        cast_events: Sequence[CombatEvent],
        buff_windows: Sequence[BuffWindow],
        dps_buckets: Sequence[DpsBucket],
        ability_name_by_id: Mapping[int, str],
    ) -> Timeline:
        casts = tuple(
            sorted(
                
                    CooldownCast(
                        timestamp_ms=event.timestamp_ms,
                        ability_id=event.ability_id,
                        ability_name=ability_name_by_id.get(
                            event.ability_id, f"ability:{event.ability_id}"
                        ),
                    )
                    for event in cast_events
                
            )
        )
        windows = tuple(sorted(buff_windows))
        buckets = tuple(sorted(dps_buckets))
        return Timeline(
            cooldown_casts=casts,
            buff_windows=windows,
            dps_buckets=buckets,
        )
