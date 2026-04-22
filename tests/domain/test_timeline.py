from __future__ import annotations

import pytest

from wowlogs_agent.domain.value_objects import (
    DPS,
    BuffWindow,
    CooldownCast,
    DpsBucket,
    Timeline,
)


class TestCooldownCast:
    def test_offset_seconds(self) -> None:
        c = CooldownCast(timestamp_ms=2500, ability_id=1, ability_name="x")
        assert c.offset_seconds == 2.5

    def test_rejects_negative_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timestamp_ms"):
            CooldownCast(timestamp_ms=-1, ability_id=1, ability_name="x")

    def test_rejects_non_positive_ability_id(self) -> None:
        with pytest.raises(ValueError, match="ability_id"):
            CooldownCast(timestamp_ms=0, ability_id=0, ability_name="x")

    def test_orders_by_timestamp(self) -> None:
        a = CooldownCast(timestamp_ms=500, ability_id=1, ability_name="x")
        b = CooldownCast(timestamp_ms=1500, ability_id=1, ability_name="x")
        assert a < b
        assert sorted([b, a]) == [a, b]


class TestBuffWindow:
    def test_duration_seconds(self) -> None:
        w = BuffWindow(start_ms=1000, end_ms=4000, ability_id=1, ability_name="x")
        assert w.duration_seconds == 3.0

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError, match="end_ms"):
            BuffWindow(start_ms=1000, end_ms=1000, ability_id=1, ability_name="x")

    def test_rejects_negative_start(self) -> None:
        with pytest.raises(ValueError, match="start_ms"):
            BuffWindow(start_ms=-1, end_ms=100, ability_id=1, ability_name="x")

    def test_rejects_non_positive_ability_id(self) -> None:
        with pytest.raises(ValueError, match="ability_id"):
            BuffWindow(start_ms=0, end_ms=100, ability_id=0, ability_name="x")


class TestDpsBucket:
    def test_duration_seconds(self) -> None:
        b = DpsBucket(start_ms=0, end_ms=10_000, dps=DPS(1000.0))
        assert b.duration_seconds == 10.0

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(ValueError, match="end_ms"):
            DpsBucket(start_ms=1000, end_ms=1000, dps=DPS(1.0))

    def test_orders_by_start(self) -> None:
        a = DpsBucket(start_ms=0, end_ms=1_000, dps=DPS(1.0))
        b = DpsBucket(start_ms=1_000, end_ms=2_000, dps=DPS(1.0))
        assert a < b


class TestTimeline:
    def test_empty_default(self) -> None:
        t = Timeline()
        assert t.is_empty
        assert t.cooldown_casts == ()
        assert t.buff_windows == ()
        assert t.dps_buckets == ()

    def test_non_empty_when_any_section_populated(self) -> None:
        t = Timeline(
            cooldown_casts=(CooldownCast(timestamp_ms=0, ability_id=1, ability_name="x"),),
        )
        assert not t.is_empty

        t2 = Timeline(
            buff_windows=(BuffWindow(start_ms=0, end_ms=1, ability_id=1, ability_name="x"),),
        )
        assert not t2.is_empty

        t3 = Timeline(
            dps_buckets=(DpsBucket(start_ms=0, end_ms=1, dps=DPS(1.0)),),
        )
        assert not t3.is_empty

    def test_equality(self) -> None:
        a = Timeline(
            cooldown_casts=(CooldownCast(timestamp_ms=0, ability_id=1, ability_name="x"),)
        )
        b = Timeline(
            cooldown_casts=(CooldownCast(timestamp_ms=0, ability_id=1, ability_name="x"),)
        )
        assert a == b
