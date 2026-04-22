from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from wowlogs_agent.domain.entities import Actor, CombatLog, Fight
from wowlogs_agent.services.log_comparator import LogComparator, LogComparisonError


def _swap_actor(log: CombatLog, new_actor: Actor) -> CombatLog:
    """Return a copy of `log` whose single fight has its actor replaced by `new_actor`.

    Preserves ability usages and damage by re-keying them to the new actor id.
    """
    fight = log.fights[0]
    old_id = fight.actors[0].id
    new_fight = Fight(
        id=fight.id,
        encounter_id=fight.encounter_id,
        encounter_name=fight.encounter_name,
        window=fight.window,
        kill=fight.kill,
        difficulty=fight.difficulty,
        actors=(new_actor,),
        ability_usages=MappingProxyType({new_actor.id: fight.ability_usages[old_id]}),
        damage_by_actor=MappingProxyType({new_actor.id: fight.damage_by_actor[old_id]}),
    )
    return replace(log, fights=(new_fight,))


class TestLogComparator:
    @staticmethod
    def _ids(higher_log: CombatLog, lower_log: CombatLog) -> dict[str, int]:
        return {
            "fight_id_a": higher_log.fights[0].id,
            "fight_id_b": lower_log.fights[0].id,
        }

    def test_compare_uses_specified_fights(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        delta = LogComparator().compare(
            higher_log,
            lower_log,
            character_a="Zug",
            **self._ids(higher_log, lower_log),
        )
        assert delta.higher.encounter_name == "Fyrakk"
        assert delta.dps_delta > 0

    def test_compare_raises_when_fight_id_missing(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        with pytest.raises(LogComparisonError, match="Fight 999"):
            LogComparator().compare(
                higher_log,
                lower_log,
                character_a="Zug",
                fight_id_a=999,
                fight_id_b=lower_log.fights[0].id,
            )

    def test_compare_rejects_cross_encounter_fight_pair(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        # Rebuild lower_log's fight with a different encounter id.
        original = lower_log.fights[0]
        other_encounter = Fight(
            id=original.id,
            encounter_id=original.encounter_id + 1,
            encounter_name="Other Boss",
            window=original.window,
            kill=original.kill,
            difficulty=original.difficulty,
            actors=original.actors,
            ability_usages=original.ability_usages,
            damage_by_actor=original.damage_by_actor,
        )
        mismatched = replace(lower_log, fights=(other_encounter,))

        with pytest.raises(LogComparisonError, match="Encounter mismatch"):
            LogComparator().compare(
                higher_log,
                mismatched,
                character_a="Zug",
                fight_id_a=higher_log.fights[0].id,
                fight_id_b=mismatched.fights[0].id,
            )

    def test_compare_raises_when_actor_missing(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        with pytest.raises(LogComparisonError):
            LogComparator().compare(
                higher_log,
                lower_log,
                character_a="NotThere",
                **self._ids(higher_log, lower_log),
            )

    def test_compare_accepts_distinct_character_names_per_log(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        delta = LogComparator().compare(
            higher_log,
            lower_log,
            character_a="Zug",
            character_b="Zug",
            **self._ids(higher_log, lower_log),
        )
        assert delta.higher.actor.name == "Zug"
        assert delta.lower.actor.name == "Zug"

    def test_compare_rejects_different_classes(
        self, higher_log: CombatLog, lower_log: CombatLog, sample_actor: Actor
    ) -> None:
        mage = replace(sample_actor, id=99, name="Wizbang", class_name="Mage")
        higher = _swap_actor(higher_log, mage)

        with pytest.raises(LogComparisonError, match="Class mismatch"):
            LogComparator().compare(
                higher,
                lower_log,
                character_a="Wizbang",
                character_b="Zug",
                fight_id_a=higher.fights[0].id,
                fight_id_b=lower_log.fights[0].id,
            )

    def test_compare_rejects_different_specs_within_same_class(
        self, higher_log: CombatLog, lower_log: CombatLog, sample_actor: Actor
    ) -> None:
        fury = replace(sample_actor, id=99, name="Smashy", spec_name="Fury")
        higher = _swap_actor(higher_log, fury)

        with pytest.raises(LogComparisonError, match="Spec mismatch"):
            LogComparator().compare(
                higher,
                lower_log,
                character_a="Smashy",
                character_b="Zug",
                fight_id_a=higher.fights[0].id,
                fight_id_b=lower_log.fights[0].id,
            )

    def test_compare_skips_spec_check_when_data_missing(
        self, higher_log: CombatLog, lower_log: CombatLog, sample_actor: Actor
    ) -> None:
        unspecced = replace(sample_actor, id=99, name="Mystery", spec_name=None)
        higher = _swap_actor(higher_log, unspecced)

        LogComparator().compare(
            higher,
            lower_log,
            character_a="Mystery",
            character_b="Zug",
            fight_id_a=higher.fights[0].id,
            fight_id_b=lower_log.fights[0].id,
        )

    def test_compare_error_message_identifies_which_log_is_missing_actor(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        with pytest.raises(LogComparisonError, match="'Ghost'"):
            LogComparator().compare(
                higher_log,
                lower_log,
                character_a="Zug",
                character_b="Ghost",
                **self._ids(higher_log, lower_log),
            )
