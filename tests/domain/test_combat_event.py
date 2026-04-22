from __future__ import annotations

import pytest

from wowlogs_agent.domain.entities import CombatEvent


class TestCombatEvent:
    def test_offset_seconds_converts_ms(self) -> None:
        assert CombatEvent(timestamp_ms=1500, ability_id=1, source_id=1).offset_seconds == 1.5

    def test_accepts_zero_timestamp(self) -> None:
        CombatEvent(timestamp_ms=0, ability_id=1, source_id=1)

    def test_rejects_negative_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timestamp_ms"):
            CombatEvent(timestamp_ms=-1, ability_id=1, source_id=1)

    def test_rejects_non_positive_ability_id(self) -> None:
        with pytest.raises(ValueError, match="ability_id"):
            CombatEvent(timestamp_ms=0, ability_id=0, source_id=1)

    def test_rejects_non_positive_source_id(self) -> None:
        with pytest.raises(ValueError, match="source_id"):
            CombatEvent(timestamp_ms=0, ability_id=1, source_id=0)

    def test_target_id_optional(self) -> None:
        e = CombatEvent(timestamp_ms=0, ability_id=1, source_id=1)
        assert e.target_id is None

    def test_equality_and_hash(self) -> None:
        a = CombatEvent(timestamp_ms=100, ability_id=5, source_id=2, target_id=9)
        b = CombatEvent(timestamp_ms=100, ability_id=5, source_id=2, target_id=9)
        assert a == b
        assert hash(a) == hash(b)

    def test_is_frozen(self) -> None:
        e = CombatEvent(timestamp_ms=0, ability_id=1, source_id=1)
        with pytest.raises(Exception):
            e.timestamp_ms = 5  # type: ignore[misc]
