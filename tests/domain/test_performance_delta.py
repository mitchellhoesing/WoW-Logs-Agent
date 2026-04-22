from __future__ import annotations

from wowlogs_agent.domain.entities import CombatLog
from wowlogs_agent.domain.performance import PerformanceDelta, PerformanceProfile


def _profile(log: CombatLog, actor_name: str) -> PerformanceProfile:
    fight = log.fights[0]
    actor = fight.actor_by_name(actor_name)
    assert actor is not None
    return PerformanceProfile.from_fight(fight, actor, log.report_id)


class TestPerformanceDelta:
    def test_normalizes_higher_and_lower(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        # Intentionally swap argument order: build() should reorder so higher.dps >= lower.dps.
        lower_profile = _profile(lower_log, "Zug")
        higher_profile = _profile(higher_log, "Zug")
        delta = PerformanceDelta.build(higher=lower_profile, lower=higher_profile)
        assert delta.higher.report_id == "AAAA"
        assert delta.lower.report_id == "BBBB"
        assert delta.dps_delta > 0

    def test_top_ability_deltas_sorted_by_abs_dps_impact(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        delta = PerformanceDelta.build(
            higher=_profile(higher_log, "Zug"),
            lower=_profile(lower_log, "Zug"),
        )
        impacts = [abs(d.dps_contribution_delta) for d in delta.ability_deltas]
        assert impacts == sorted(impacts, reverse=True)

    def test_includes_abilities_present_only_in_one_run(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        delta = PerformanceDelta.build(
            higher=_profile(higher_log, "Zug"),
            lower=_profile(lower_log, "Zug"),
        )
        # Whirlwind exists only in the lower-DPS run.
        whirlwind = next(d for d in delta.ability_deltas if d.ability_id == 103)
        assert whirlwind.higher is None
        assert whirlwind.lower is not None
