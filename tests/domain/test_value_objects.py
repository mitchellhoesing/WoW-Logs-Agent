from __future__ import annotations

import pytest

from wowlogs_agent.domain.value_objects import DPS, TimeWindow, Uptime


class TestDPS:
    def test_from_total_divides(self) -> None:
        assert DPS.from_total(1000.0, 10.0) == DPS(100.0)

    def test_rejects_negative(self) -> None:
        with pytest.raises(ValueError):
            DPS(-1.0)

    def test_pct_change_handles_zero_baseline(self) -> None:
        assert DPS(100.0).pct_change_from(DPS(0.0)) == 0.0

    def test_ordering(self) -> None:
        assert DPS(50.0) < DPS(100.0)


class TestUptime:
    def test_from_seconds_clamps(self) -> None:
        # Guards against float overshoot from upstream aggregation.
        assert Uptime.from_seconds(11.0, 10.0).fraction == 1.0

    def test_percent(self) -> None:
        assert Uptime(0.5).percent == 50.0

    def test_rejects_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            Uptime(1.5)


class TestTimeWindow:
    def test_duration(self) -> None:
        w = TimeWindow(0, 5000)
        assert w.duration_ms == 5000
        assert w.duration_seconds == 5.0

    def test_contains_is_half_open(self) -> None:
        w = TimeWindow(0, 100)
        assert w.contains(0)
        assert not w.contains(100)

    def test_overlap(self) -> None:
        a = TimeWindow(0, 100)
        b = TimeWindow(50, 200)
        assert a.overlap(b) == 50

    def test_rejects_inverted(self) -> None:
        with pytest.raises(ValueError):
            TimeWindow(10, 10)
