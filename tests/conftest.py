from __future__ import annotations

from types import MappingProxyType

import pytest

from wowlogs_agent.domain.entities import AbilityUsage, Actor, ActorRole, CombatLog, Fight
from wowlogs_agent.domain.value_objects import TimeWindow


def _usage(ability_id: int, name: str, casts: int, damage: int, duration: float) -> AbilityUsage:
    return AbilityUsage(
        ability_id=ability_id,
        name=name,
        casts=casts,
        hits=casts,
        total_damage=damage,
        active_seconds=0.0,
        fight_duration_seconds=duration,
    )


@pytest.fixture
def sample_actor() -> Actor:
    return Actor(id=1, name="Zug", role=ActorRole.DPS, class_name="Warrior", spec_name="Arms")


@pytest.fixture
def higher_log(sample_actor: Actor) -> CombatLog:
    duration = 300.0
    window = TimeWindow(0, int(duration * 1000))
    usages = (
        _usage(100, "Mortal Strike", 40, 1_500_000, duration),
        _usage(101, "Bladestorm", 5, 900_000, duration),
        _usage(102, "Execute", 30, 1_100_000, duration),
    )
    fight = Fight(
        id=7,
        encounter_id=42,
        encounter_name="Fyrakk",
        window=window,
        kill=True,
        difficulty=5,
        actors=(sample_actor,),
        ability_usages=MappingProxyType({sample_actor.id: usages}),
        damage_by_actor=MappingProxyType({sample_actor.id: 3_500_000}),
    )
    return CombatLog(
        report_id="AAAA",
        title="Good Pull",
        owner="Zug",
        start_unix_ms=0,
        zone_name="Amirdrassil",
        fights=(fight,),
    )


@pytest.fixture
def lower_log(sample_actor: Actor) -> CombatLog:
    duration = 310.0
    window = TimeWindow(0, int(duration * 1000))
    usages = (
        _usage(100, "Mortal Strike", 30, 1_000_000, duration),
        _usage(101, "Bladestorm", 3, 500_000, duration),
        _usage(102, "Execute", 28, 1_000_000, duration),
        _usage(103, "Whirlwind", 10, 200_000, duration),
    )
    fight = Fight(
        id=9,
        encounter_id=42,
        encounter_name="Fyrakk",
        window=window,
        kill=True,
        difficulty=5,
        actors=(sample_actor,),
        ability_usages=MappingProxyType({sample_actor.id: usages}),
        damage_by_actor=MappingProxyType({sample_actor.id: 2_700_000}),
    )
    return CombatLog(
        report_id="BBBB",
        title="Bad Pull",
        owner="Zug",
        start_unix_ms=0,
        zone_name="Amirdrassil",
        fights=(fight,),
    )
