from __future__ import annotations

from wowlogs_agent.domain.entities import CombatEvent
from wowlogs_agent.domain.value_objects import DPS, BuffWindow, DpsBucket
from wowlogs_agent.services import TimelineBuilder


class TestTimelineBuilder:
    def test_builds_empty_timeline_from_empty_inputs(self) -> None:
        t = TimelineBuilder().build(
            cast_events=(),
            buff_windows=(),
            dps_buckets=(),
            ability_name_by_id={},
        )
        assert t.is_empty

    def test_names_casts_from_name_map(self) -> None:
        events = [CombatEvent(timestamp_ms=1000, ability_id=42, source_id=1)]
        t = TimelineBuilder().build(
            cast_events=events,
            buff_windows=(),
            dps_buckets=(),
            ability_name_by_id={42: "Avenging Wrath"},
        )
        assert len(t.cooldown_casts) == 1
        assert t.cooldown_casts[0].ability_name == "Avenging Wrath"
        assert t.cooldown_casts[0].ability_id == 42
        assert t.cooldown_casts[0].timestamp_ms == 1000

    def test_falls_back_to_synthetic_name_when_unknown(self) -> None:
        events = [CombatEvent(timestamp_ms=0, ability_id=999, source_id=1)]
        t = TimelineBuilder().build(
            cast_events=events,
            buff_windows=(),
            dps_buckets=(),
            ability_name_by_id={},
        )
        assert t.cooldown_casts[0].ability_name == "ability:999"

    def test_sorts_casts_by_timestamp(self) -> None:
        events = [
            CombatEvent(timestamp_ms=3000, ability_id=1, source_id=1),
            CombatEvent(timestamp_ms=500, ability_id=1, source_id=1),
            CombatEvent(timestamp_ms=1500, ability_id=1, source_id=1),
        ]
        t = TimelineBuilder().build(
            cast_events=events,
            buff_windows=(),
            dps_buckets=(),
            ability_name_by_id={1: "Cast"},
        )
        assert [c.timestamp_ms for c in t.cooldown_casts] == [500, 1500, 3000]

    def test_passes_through_buff_windows_and_buckets_sorted(self) -> None:
        windows = [
            BuffWindow(start_ms=5000, end_ms=6000, ability_id=1, ability_name="x"),
            BuffWindow(start_ms=1000, end_ms=2000, ability_id=1, ability_name="x"),
        ]
        buckets = [
            DpsBucket(start_ms=10_000, end_ms=20_000, dps=DPS(2000.0)),
            DpsBucket(start_ms=0, end_ms=10_000, dps=DPS(1000.0)),
        ]
        t = TimelineBuilder().build(
            cast_events=(),
            buff_windows=windows,
            dps_buckets=buckets,
            ability_name_by_id={},
        )
        assert [w.start_ms for w in t.buff_windows] == [1000, 5000]
        assert [b.start_ms for b in t.dps_buckets] == [0, 10_000]

    def test_deterministic_output_for_same_input(self) -> None:
        events = [
            CombatEvent(timestamp_ms=500, ability_id=1, source_id=1),
            CombatEvent(timestamp_ms=1500, ability_id=2, source_id=1),
        ]
        names = {1: "A", 2: "B"}
        builder = TimelineBuilder()
        a = builder.build(
            cast_events=events, buff_windows=(), dps_buckets=(), ability_name_by_id=names
        )
        b = builder.build(
            cast_events=events, buff_windows=(), dps_buckets=(), ability_name_by_id=names
        )
        assert a == b

    def test_returns_tuples_not_lists(self) -> None:
        t = TimelineBuilder().build(
            cast_events=[CombatEvent(timestamp_ms=0, ability_id=1, source_id=1)],
            buff_windows=[BuffWindow(start_ms=0, end_ms=1, ability_id=1, ability_name="x")],
            dps_buckets=[DpsBucket(start_ms=0, end_ms=1, dps=DPS(1.0))],
            ability_name_by_id={1: "A"},
        )
        assert isinstance(t.cooldown_casts, tuple)
        assert isinstance(t.buff_windows, tuple)
        assert isinstance(t.dps_buckets, tuple)
