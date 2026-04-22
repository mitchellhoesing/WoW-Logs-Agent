from __future__ import annotations

import json

from wowlogs_agent.domain.entities import CombatLog
from wowlogs_agent.services.context_builder import AnalysisContextBuilder
from wowlogs_agent.services.log_comparator import LogComparator


class TestAnalysisContextBuilder:
    def test_build_json_is_deterministic(
        self, higher_log: CombatLog, lower_log: CombatLog
    ) -> None:
        delta = LogComparator().compare(
            higher_log,
            lower_log,
            character_a="Zug",
            fight_id_a=higher_log.fights[0].id,
            fight_id_b=lower_log.fights[0].id,
        )
        builder = AnalysisContextBuilder()
        a = builder.build_json(delta)
        b = builder.build_json(delta)
        assert a == b
        parsed = json.loads(a)
        assert parsed["encounter"] == "Fyrakk"
        assert parsed["fights"]["higher_dps_run"]["character"]["name"] == "Zug"
        assert parsed["fights"]["lower_dps_run"]["character"]["name"] == "Zug"
        assert parsed["summary"]["dps_delta"] > 0
        assert len(parsed["top_ability_deltas"]) >= 3
