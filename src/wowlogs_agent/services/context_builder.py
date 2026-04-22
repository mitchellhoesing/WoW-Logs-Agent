from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from wowlogs_agent.domain.performance import AbilityDelta, PerformanceDelta, PerformanceProfile
from wowlogs_agent.domain.value_objects import Timeline


@dataclass(frozen=True)
class AnalysisContextBuilder:
    """Converts a PerformanceDelta into a deterministic JSON payload for the LLM.

    Determinism matters: same input → byte-identical output, so runs are reproducible.
    """

    top_abilities: int = 15

    def build(self, delta: PerformanceDelta) -> Mapping[str, Any]:
        payload: dict[str, Any] = {
            "encounter": delta.higher.encounter_name,
            "summary": {
                "higher_dps": round(delta.higher.dps.value, 1),
                "lower_dps": round(delta.lower.dps.value, 1),
                "dps_delta": round(delta.dps_delta, 1),
                "dps_pct_change": round(delta.dps_pct_change * 100.0, 2),
                "higher_duration_s": round(delta.higher.duration_seconds, 1),
                "lower_duration_s": round(delta.lower.duration_seconds, 1),
                "duration_delta_s": round(delta.duration_delta_seconds, 1),
            },
            "fights": {
                "higher_dps_run": self._profile_brief(delta.higher),
                "lower_dps_run": self._profile_brief(delta.lower),
            },
            "top_ability_deltas": [
                self._ability_row(d) for d in delta.top_ability_deltas(self.top_abilities)
            ],
        }
        timelines = self._timelines_section(delta)
        if timelines is not None:
            payload["timelines"] = timelines
        return payload

    def build_json(self, delta: PerformanceDelta) -> str:
        return json.dumps(self.build(delta), indent=2, sort_keys=True)

    @staticmethod
    def _profile_brief(p: PerformanceProfile) -> Mapping[str, Any]:
        return {
            "report_id": p.report_id,
            "fight_id": p.fight_id,
            "duration_s": round(p.duration_seconds, 1),
            "dps": round(p.dps.value, 1),
            "character": {
                "name": p.actor.name,
                "class_spec": p.actor.class_spec,
                "role": p.actor.role.value,
                "item_level": p.actor.item_level,
            },
        }

    @classmethod
    def _timelines_section(cls, delta: PerformanceDelta) -> Mapping[str, Any] | None:
        """Emit per-side timeline summaries. Omitted entirely when both sides lack one.

        Token-bounded by construction: buff windows and DPS buckets are naturally
        few (dozens each); casts scale with fight length but stay compact because
        each row is ~60 bytes of JSON.
        """
        hi = cls._render_timeline(delta.higher.timeline)
        lo = cls._render_timeline(delta.lower.timeline)
        if hi is None and lo is None:
            return None
        return {
            "higher_dps_run": hi if hi is not None else cls._empty_timeline(),
            "lower_dps_run": lo if lo is not None else cls._empty_timeline(),
        }

    @staticmethod
    def _render_timeline(timeline: Timeline | None) -> Mapping[str, Any] | None:
        if timeline is None or timeline.is_empty:
            return None
        return {
            "cooldown_casts": [
                {
                    "offset_s": round(c.offset_seconds, 1),
                    "ability_id": c.ability_id,
                    "ability_name": c.ability_name,
                }
                for c in timeline.cooldown_casts
            ],
            "buff_windows": [
                {
                    "start_s": round(w.start_ms / 1000.0, 1),
                    "end_s": round(w.end_ms / 1000.0, 1),
                    "duration_s": round(w.duration_seconds, 1),
                    "ability_id": w.ability_id,
                    "ability_name": w.ability_name,
                }
                for w in timeline.buff_windows
            ],
            "dps_buckets": [
                {
                    "start_s": round(b.start_ms / 1000.0, 1),
                    "end_s": round(b.end_ms / 1000.0, 1),
                    "dps": round(b.dps.value, 1),
                }
                for b in timeline.dps_buckets
            ],
        }

    @staticmethod
    def _empty_timeline() -> Mapping[str, Any]:
        return {"cooldown_casts": [], "buff_windows": [], "dps_buckets": []}

    @staticmethod
    def _ability_row(d: AbilityDelta) -> Mapping[str, Any]:
        def side(u: Any) -> Mapping[str, Any] | None:
            if u is None:
                return None
            return {
                "casts": u.casts,
                "total_damage": u.total_damage,
                "uptime_pct": round(u.uptime.percent, 1),
                "dps_contribution": round(u.dps_contribution.value, 1),
            }

        return {
            "ability_id": d.ability_id,
            "name": d.name,
            "casts_delta": d.casts_delta,
            "damage_delta": d.damage_delta,
            "uptime_delta_pct": round(d.uptime_delta * 100.0, 2),
            "dps_contribution_delta": round(d.dps_contribution_delta, 1),
            "higher_dps_run": side(d.higher),
            "lower_dps_run": side(d.lower),
        }
