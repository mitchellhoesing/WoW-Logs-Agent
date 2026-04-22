from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> Mapping[str, Any]:
    with (_FIXTURES / name).open(encoding="utf-8") as fp:
        return cast(Mapping[str, Any], json.load(fp))

from wowlogs_agent.gateways.warcraft_logs.graphql_client import WarcraftLogsGraphQLClient
from wowlogs_agent.gateways.warcraft_logs.graphql_combat_log_repository import (
    GraphQLCombatLogRepository,
)
from wowlogs_agent.gateways.warcraft_logs.queries import (
    FIGHT_ACTOR_CASTS_QUERY,
    FIGHT_ACTOR_DAMAGE_QUERY,
    FIGHT_BUFF_TABLE_QUERY,
    FIGHT_CAST_EVENTS_QUERY,
    FIGHT_DAMAGE_GRAPH_QUERY,
    FIGHT_DAMAGE_TABLE_QUERY,
    FIGHT_PLAYER_DETAILS_QUERY,
    REPORT_SUMMARY_QUERY,
)


class FakeGraphQLClient:
    """Minimal in-memory stand-in that routes queries by their constant identity."""

    def __init__(self, responses: dict[str, Mapping[str, Any]]) -> None:
        self._responses = responses
        self.call_counts: dict[str, int] = {}

    def execute(
        self,
        query: str,
        variables: Mapping[str, Any],
        *,
        cache_namespace: str,
    ) -> Mapping[str, Any]:
        if query is REPORT_SUMMARY_QUERY:
            return self._record("summary", self._responses["summary"])
        if query is FIGHT_DAMAGE_TABLE_QUERY:
            return self._record("damage_summary", self._responses["damage_summary"])
        if query is FIGHT_ACTOR_DAMAGE_QUERY:
            return self._record("actor_damage", self._responses.get("actor_damage", _empty_table()))
        if query is FIGHT_ACTOR_CASTS_QUERY:
            return self._record("actor_casts", self._responses.get("actor_casts", _empty_table()))
        if query is FIGHT_BUFF_TABLE_QUERY:
            return self._record("buffs", self._responses["buffs"])
        if query is FIGHT_PLAYER_DETAILS_QUERY:
            return self._record(
                "fight_players",
                self._responses.get("fight_players", _empty_fight_players()),
            )
        if query is FIGHT_CAST_EVENTS_QUERY:
            return self._record(
                "cast_events",
                self._paged_cast_events(variables.get("start")),
            )
        if query is FIGHT_DAMAGE_GRAPH_QUERY:
            return self._record(
                "damage_graph",
                self._responses.get("damage_graph", _empty_damage_graph()),
            )
        raise AssertionError(f"unexpected query via {cache_namespace}")

    def _record(self, key: str, value: Mapping[str, Any]) -> Mapping[str, Any]:
        self.call_counts[key] = self.call_counts.get(key, 0) + 1
        return value

    def _paged_cast_events(self, cursor: Any) -> Mapping[str, Any]:
        """Route cast-event queries to the right page.

        Tests that set a single `cast_events` response hit it on every page;
        tests that set `cast_events_pages` (a list) advance one page per call —
        the linear index is the number of prior cast-event calls, which is
        exactly `call_counts.get("cast_events", 0)` at this point (this runs
        before `_record` increments the counter).
        """
        pages = self._responses.get("cast_events_pages")
        if isinstance(pages, list) and pages:
            idx = min(self.call_counts.get("cast_events", 0), len(pages) - 1)
            return pages[idx]
        return self._responses.get("cast_events", _empty_cast_events())


def _empty_table() -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {"report": {"table": {"data": {"entries": []}}}}
        }
    }


def _empty_fight_players() -> Mapping[str, Any]:
    return {"data": {"reportData": {"report": {"playerDetails": None}}}}


def _empty_cast_events() -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {
                "report": {"events": {"data": [], "nextPageTimestamp": None}}
            }
        }
    }


def _empty_damage_graph() -> Mapping[str, Any]:
    return {"data": {"reportData": {"report": {"graph": {"data": {"series": []}}}}}}


def _cast_events(events: list[dict[str, Any]], next_page: float | None = None) -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {
                "report": {
                    "events": {"data": events, "nextPageTimestamp": next_page}
                }
            }
        }
    }


def _damage_graph(points: list[tuple[int, int]], point_interval: int = 10_000) -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {
                "report": {
                    "graph": {
                        "data": {
                            "series": [{"data": [[x, y] for x, y in points]}],
                            "pointInterval": point_interval,
                        }
                    }
                }
            }
        }
    }


def _fight_players(player_details: Any) -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {"report": {"playerDetails": player_details}}
        }
    }


def _actor_damage(abilities: list[dict[str, Any]]) -> Mapping[str, Any]:
    """Ability-pivoted DamageDone response: one entry per ability."""
    return {
        "data": {
            "reportData": {
                "report": {
                    "table": {"data": {"entries": abilities}}
                }
            }
        }
    }


def _actor_casts(castings: dict[int, int]) -> Mapping[str, Any]:
    """Ability-pivoted Casts response: one entry per ability with total=cast count."""
    return {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"guid": aid, "total": count}
                                for aid, count in castings.items()
                            ]
                        }
                    }
                }
            }
        }
    }


def _summary() -> Mapping[str, Any]:
    return {
        "data": {
            "reportData": {
                "report": {
                    "code": "REPORT1",
                    "title": "Test Raid",
                    "owner": {"name": "Zug"},
                    "startTime": 0,
                    "zone": {"name": "Amirdrassil"},
                    "masterData": {
                        "actors": [{"id": 10, "name": "Zug", "subType": "Warrior"}],
                        "abilities": [],
                    },
                    "fights": [
                        {
                            "id": 1,
                            "encounterID": 42,
                            "name": "Fyrakk",
                            "startTime": 0,
                            "endTime": 300_000,  # 300s
                            "kill": True,
                            "difficulty": 5,
                            "friendlyPlayers": [10],
                        }
                    ],
                }
            }
        }
    }


def _damage_summary() -> Mapping[str, Any]:
    """Per-source summary — only the actor's `total` is consumed now."""
    return {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "entries": [
                                {"id": 10, "total": 3_000_000},
                            ]
                        }
                    }
                }
            }
        }
    }


def _buffs(
    bladestorm_uptime_ms: int,
    *,
    bands: list[tuple[int, int]] | None = None,
) -> Mapping[str, Any]:
    aura: dict[str, Any] = {
        "guid": 227847,
        "name": "Bladestorm",
        "totalUptime": bladestorm_uptime_ms,
    }
    if bands is not None:
        aura["bands"] = [
            {"startTime": start, "endTime": end} for start, end in bands
        ]
    return {
        "data": {
            "reportData": {
                "report": {
                    "table": {
                        "data": {
                            "auras": [aura]
                        }
                    }
                }
            }
        }
    }


def _default_actor_damage() -> Mapping[str, Any]:
    return _actor_damage(
        [
            {
                "guid": 227847,
                "name": "Bladestorm",
                "hitCount": 40,
                "total": 1_200_000,
            },
            {
                "guid": 12294,
                "name": "Mortal Strike",
                "hitCount": 30,
                "total": 1_800_000,
            },
        ]
    )


class TestBuffUptimeFlowsIntoAbilityUsage:
    def test_uptime_populated_from_buff_table(self) -> None:
        fake = FakeGraphQLClient(
            {
                "summary": _summary(),
                "damage_summary": _damage_summary(),
                "actor_damage": _default_actor_damage(),
                "actor_casts": _actor_casts({227847: 5, 12294: 30}),
                "buffs": _buffs(bladestorm_uptime_ms=60_000),  # 60s on a 300s fight
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        log = repo.fetch("REPORT1", character_name="Zug")
        fight = log.fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None

        bladestorm = next(
            u for u in fight.ability_usages_for(zug.id) if u.ability_id == 227847
        )
        mortal_strike = next(
            u for u in fight.ability_usages_for(zug.id) if u.ability_id == 12294
        )

        # 60s / 300s → 20% uptime for the aura-producing ability.
        assert round(bladestorm.uptime.percent, 1) == 20.0
        # No buff-table entry → stays at 0% (instant damage spell).
        assert mortal_strike.uptime.percent == 0.0

    def test_uptime_clamped_to_fight_duration(self) -> None:
        # Defensive: if WCL ever returns an uptime > fight duration, we clamp so
        # Uptime.from_seconds stays in [0,1].
        fake = FakeGraphQLClient(
            {
                "summary": _summary(),
                "damage_summary": _damage_summary(),
                "actor_damage": _default_actor_damage(),
                "actor_casts": _actor_casts({227847: 5, 12294: 30}),
                "buffs": _buffs(bladestorm_uptime_ms=500_000),  # 500s > 300s fight
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        log = repo.fetch("REPORT1", character_name="Zug")
        fight = log.fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        bladestorm = next(
            u for u in fight.ability_usages_for(zug.id) if u.ability_id == 227847
        )
        assert bladestorm.uptime.fraction == 1.0


class TestCastCounts:
    def test_casts_come_from_casts_table(self) -> None:
        fake = FakeGraphQLClient(
            {
                "summary": _summary(),
                "damage_summary": _damage_summary(),
                "actor_damage": _default_actor_damage(),  # Bladestorm hits 40x (7 per cast)
                "actor_casts": _actor_casts({227847: 5, 12294: 30}),  # Bladestorm cast 5x
                "buffs": _buffs(0),
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        usages = {u.ability_id: u for u in fight.ability_usages_for(zug.id)}

        # Casts table supplies the real cast count; hits still come from damage.
        assert usages[227847].casts == 5
        assert usages[227847].hits == 40
        assert usages[12294].casts == 30
        assert usages[12294].hits == 30

    def test_ability_present_in_casts_but_not_damage_still_surfaces(self) -> None:
        """Scenario this fix was written for: an ability the player cast many
        times but whose damage total put it outside one summary's top-N. The
        scoped Casts table lists the ability; the damage breakdown does too
        once truncation is off, but we also want the merge to tolerate a cast
        appearing without a matching damage row (absorbed / dispelled casts)."""
        fake = FakeGraphQLClient(
            {
                "summary": _summary(),
                "damage_summary": _damage_summary(),
                "actor_damage": _actor_damage([]),  # no damage recorded at all
                "actor_casts": _actor_casts({105174: 53}),  # Hand of Gul'dan, 53 casts
                "buffs": _buffs(0),
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        usages = {u.ability_id: u for u in fight.ability_usages_for(zug.id)}

        assert 105174 in usages
        assert usages[105174].casts == 53
        assert usages[105174].total_damage == 0

    def test_non_target_actors_get_no_ability_usages(self) -> None:
        """Per-ability breakdowns are expensive and only consumed for the
        compared character. Other actors in the fight should end up with an
        empty usage list — the scoped damage/casts queries shouldn't fire."""
        summary = _summary()
        # Add a second actor to the roster.
        summary["data"]["reportData"]["report"]["masterData"]["actors"].append(  # type: ignore[index]
            {"id": 11, "name": "Other", "subType": "Mage"}
        )
        summary["data"]["reportData"]["report"]["fights"][0]["friendlyPlayers"] = [10, 11]  # type: ignore[index]
        damage_summary = _damage_summary()
        damage_summary["data"]["reportData"]["report"]["table"]["data"]["entries"].append(  # type: ignore[index]
            {"id": 11, "total": 2_000_000}
        )

        fake = FakeGraphQLClient(
            {
                "summary": summary,
                "damage_summary": damage_summary,
                "actor_damage": _default_actor_damage(),
                "actor_casts": _actor_casts({227847: 5, 12294: 30}),
                "buffs": _buffs(0),
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        other = fight.actor_by_name("Other")
        assert other is not None
        assert fight.ability_usages_for(other.id) == ()


class TestActorSpecParsing:
    @staticmethod
    def _fetch_with_actor(raw_actor: dict[str, Any]) -> Any:
        summary = _summary()
        report = summary["data"]["reportData"]["report"]  # type: ignore[index]
        report["masterData"]["actors"] = [raw_actor]
        report["fights"][0]["friendlyPlayers"] = [raw_actor["id"]]
        damage_summary = _damage_summary()
        damage_summary["data"]["reportData"]["report"]["table"]["data"]["entries"][0]["id"] = (  # type: ignore[index]
            raw_actor["id"]
        )
        fake = FakeGraphQLClient(
            {
                "summary": summary,
                "damage_summary": damage_summary,
                "buffs": _buffs(0),
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))
        return repo.fetch("REPORT1").fights[0].actors[0]

    def test_derives_spec_from_icon(self) -> None:
        actor = self._fetch_with_actor(
            {"id": 10, "name": "Zug", "subType": "Warrior", "icon": "Warrior-Arms"}
        )
        assert actor.class_name == "Warrior"
        assert actor.spec_name == "Arms"

    def test_spec_is_none_when_icon_missing(self) -> None:
        actor = self._fetch_with_actor({"id": 10, "name": "Zug", "subType": "Warrior"})
        assert actor.class_name == "Warrior"
        assert actor.spec_name is None

    def test_spec_is_none_when_icon_has_no_dash(self) -> None:
        actor = self._fetch_with_actor(
            {"id": 10, "name": "Zug", "subType": "Warrior", "icon": "Warrior"}
        )
        assert actor.spec_name is None

    def test_class_falls_back_to_icon_prefix_when_subtype_missing(self) -> None:
        actor = self._fetch_with_actor(
            {"id": 10, "name": "Zug", "icon": "Mage-Frost"}
        )
        assert actor.class_name == "Mage"
        assert actor.spec_name == "Frost"


class TestPlayerDetailsEnrichment:
    @staticmethod
    def _summary_with_player_details(player_details: Any) -> Mapping[str, Any]:
        summary = _summary()
        summary["data"]["reportData"]["report"]["playerDetails"] = player_details  # type: ignore[index]
        return summary

    @staticmethod
    def _fetch(summary: Mapping[str, Any]) -> Any:
        fake = FakeGraphQLClient(
            {
                "summary": summary,
                "damage_summary": _damage_summary(),
                "buffs": _buffs(0),
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))
        return repo.fetch("REPORT1").fights[0].actors[0]

    def test_spec_and_role_populated_from_player_details(self) -> None:
        details = {
            "data": {
                "dps": [
                    {
                        "id": 10,
                        "name": "Zug",
                        "type": "Warlock",
                        "specs": [{"spec": "Destruction", "role": "dps"}],
                    }
                ]
            }
        }
        actor = self._fetch(self._summary_with_player_details(details))
        assert actor.spec_name == "Destruction"
        assert actor.class_name == "Warlock"
        assert actor.role.value == "dps"

    def test_healer_role_mapped_from_healers_bucket(self) -> None:
        details = {
            "data": {
                "healers": [
                    {
                        "id": 10,
                        "name": "Zug",
                        "type": "Priest",
                        "specs": [{"spec": "Holy", "role": "healer"}],
                    }
                ]
            }
        }
        actor = self._fetch(self._summary_with_player_details(details))
        assert actor.spec_name == "Holy"
        assert actor.role.value == "healer"

    def test_player_details_overrides_icon_spec_when_both_present(self) -> None:
        # Icon claims Arms, playerDetails says Fury — playerDetails wins.
        summary = _summary()
        summary["data"]["reportData"]["report"]["masterData"]["actors"] = [  # type: ignore[index]
            {"id": 10, "name": "Zug", "subType": "Warrior", "icon": "Warrior-Arms"}
        ]
        summary["data"]["reportData"]["report"]["playerDetails"] = {  # type: ignore[index]
            "data": {
                "dps": [
                    {
                        "id": 10,
                        "name": "Zug",
                        "type": "Warrior",
                        "specs": [{"spec": "Fury", "role": "dps"}],
                    }
                ]
            }
        }
        actor = self._fetch(summary)
        assert actor.spec_name == "Fury"

    def test_picks_dominant_spec_by_count_not_list_order(self) -> None:
        # Unsorted specs list: Demo listed first but Destruction has higher count.
        details = {
            "data": {
                "playerDetails": {
                    "dps": [
                        {
                            "id": 10,
                            "name": "Zug",
                            "type": "Warlock",
                            "specs": [
                                {"spec": "Demonology", "count": 1},
                                {"spec": "Destruction", "count": 6},
                            ],
                        }
                    ]
                }
            }
        }
        actor = self._fetch(self._summary_with_player_details(details))
        assert actor.spec_name == "Destruction"

    def test_handles_double_wrapped_player_details_payload(self) -> None:
        # Matches the actual WCL shape: data → playerDetails → {dps, healers, tanks}.
        details = {
            "data": {
                "playerDetails": {
                    "dps": [
                        {
                            "id": 10,
                            "name": "Zug",
                            "type": "Warlock",
                            "specs": [{"spec": "Destruction"}],
                        }
                    ]
                }
            }
        }
        actor = self._fetch(self._summary_with_player_details(details))
        assert actor.spec_name == "Destruction"
        assert actor.role.value == "dps"

    def test_per_fight_player_details_override_report_level_spec(self) -> None:
        # Report-level dominant spec is Destruction (6 vs 1 Demonology), but the
        # fight being fetched had the player in Demonology. Per-fight payload
        # must win so spec-compatibility checks see what was actually played.
        summary = _summary()
        summary["data"]["reportData"]["report"]["playerDetails"] = {  # type: ignore[index]
            "data": {
                "dps": [
                    {
                        "id": 10,
                        "name": "Zug",
                        "type": "Warlock",
                        "specs": [
                            {"spec": "Demonology", "count": 1},
                            {"spec": "Destruction", "count": 6},
                        ],
                    }
                ]
            }
        }
        fight_players = _fight_players(
            {
                "data": {
                    "dps": [
                        {
                            "id": 10,
                            "name": "Zug",
                            "type": "Warlock",
                            "specs": [{"spec": "Demonology", "count": 1}],
                        }
                    ]
                }
            }
        )
        fake = FakeGraphQLClient(
            {
                "summary": summary,
                "damage_summary": _damage_summary(),
                "buffs": _buffs(0),
                "fight_players": fight_players,
            }
        )
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))
        actor = repo.fetch("REPORT1").fights[0].actors[0]
        assert actor.spec_name == "Demonology"

    def test_missing_player_details_leaves_icon_fallback(self) -> None:
        # No playerDetails at all: spec still derived from icon.
        summary = _summary()
        summary["data"]["reportData"]["report"]["masterData"]["actors"] = [  # type: ignore[index]
            {"id": 10, "name": "Zug", "subType": "Warrior", "icon": "Warrior-Arms"}
        ]
        actor = self._fetch(summary)
        assert actor.spec_name == "Arms"


class TestTimelineAssembly:
    """Covers the new events + graph adapter plumbing.

    These tests lock in three invariants from the plan:
      (a) the cast-events pagination loop terminates and concatenates pages,
      (b) buff bands come out of the existing Buffs response — no extra fetch,
      (c) the full per-character fetch issues exactly 2 new calls (cast_events +
          damage_graph) on top of today's baseline.
    """

    @staticmethod
    def _base_responses() -> dict[str, Any]:
        return {
            "summary": _summary(),
            "damage_summary": _damage_summary(),
            "actor_damage": _default_actor_damage(),
            "actor_casts": _actor_casts({227847: 5, 12294: 30}),
            # Two buff activations: 10s–20s and 100s–112s on the 300s fight.
            "buffs": _buffs(
                bladestorm_uptime_ms=22_000,
                bands=[(10_000, 20_000), (100_000, 112_000)],
            ),
            "damage_graph": _load_fixture("damage_graph.json"),
        }

    def test_pagination_concatenates_cast_events_across_pages(self) -> None:
        responses = self._base_responses()
        responses["cast_events_pages"] = [
            _load_fixture("cast_events_page_1.json"),
            _load_fixture("cast_events_page_2.json"),
        ]
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        timeline = fight.timeline_for(zug.id)
        assert timeline is not None

        # All four casts survived pagination; sorted by timestamp.
        assert [c.timestamp_ms for c in timeline.cooldown_casts] == [1500, 4200, 5800, 9100]
        # Pagination loop ran until nextPageTimestamp was null — two calls.
        assert fake.call_counts.get("cast_events") == 2

    def test_single_page_terminates_after_one_call(self) -> None:
        responses = self._base_responses()
        responses["cast_events"] = _cast_events(
            [
                {"timestamp": 500, "sourceID": 10, "abilityGameID": 12294},
            ],
            next_page=None,
        )
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        timeline = fight.timeline_for(zug.id)
        assert timeline is not None
        assert len(timeline.cooldown_casts) == 1
        assert fake.call_counts.get("cast_events") == 1

    def test_buff_bands_extracted_without_extra_buff_fetch(self) -> None:
        responses = self._base_responses()
        responses["cast_events"] = _cast_events([], next_page=None)
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        timeline = fight.timeline_for(zug.id)
        assert timeline is not None

        # Two bands in the Buffs response → two BuffWindow entries on the timeline.
        assert [(w.start_ms, w.end_ms) for w in timeline.buff_windows] == [
            (10_000, 20_000),
            (100_000, 112_000),
        ]
        # Critically: exactly one buff table fetch was issued — the band parser
        # piggybacked on the uptime parser's response.
        assert fake.call_counts.get("buffs") == 1

    def test_damage_graph_populates_dps_buckets(self) -> None:
        responses = self._base_responses()
        responses["cast_events"] = _cast_events([], next_page=None)
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        zug = fight.actor_by_name("Zug")
        assert zug is not None
        timeline = fight.timeline_for(zug.id)
        assert timeline is not None

        assert [b.start_ms for b in timeline.dps_buckets] == [0, 10_000, 20_000]
        assert all(b.duration_seconds == 10.0 for b in timeline.dps_buckets)
        # Fixture y=1_000_000 per 10s bucket → 100_000 DPS.
        assert timeline.dps_buckets[0].dps.value == 100_000.0
        assert fake.call_counts.get("damage_graph") == 1

    def test_full_fetch_issues_exactly_two_new_calls_beyond_baseline(self) -> None:
        """Baseline (today): summary, damage_summary, fight_players, actor_damage,
        actor_casts, buffs. New adapter adds: cast_events, damage_graph."""
        responses = self._base_responses()
        responses["cast_events"] = _cast_events([], next_page=None)
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        repo.fetch("REPORT1", character_name="Zug")

        # Baseline: one of each query per (fight, target).
        for baseline_key in (
            "summary",
            "damage_summary",
            "actor_damage",
            "actor_casts",
            "buffs",
        ):
            assert fake.call_counts.get(baseline_key) == 1, baseline_key
        # Exactly two new call types beyond the baseline.
        assert fake.call_counts.get("cast_events") == 1
        assert fake.call_counts.get("damage_graph") == 1

    def test_non_target_actor_has_no_timeline(self) -> None:
        """The timeline is scoped to the compared character — other actors in
        the fight must not trigger cast-event or graph fetches."""
        summary = _summary()
        summary["data"]["reportData"]["report"]["masterData"]["actors"].append(  # type: ignore[index]
            {"id": 11, "name": "Other", "subType": "Mage"}
        )
        summary["data"]["reportData"]["report"]["fights"][0]["friendlyPlayers"] = [10, 11]  # type: ignore[index]
        damage_summary = _damage_summary()
        damage_summary["data"]["reportData"]["report"]["table"]["data"]["entries"].append(  # type: ignore[index]
            {"id": 11, "total": 2_000_000}
        )
        responses = self._base_responses()
        responses["summary"] = summary
        responses["damage_summary"] = damage_summary
        responses["cast_events"] = _cast_events([], next_page=None)
        fake = FakeGraphQLClient(responses)
        repo = GraphQLCombatLogRepository(client=cast(WarcraftLogsGraphQLClient, fake))

        fight = repo.fetch("REPORT1", character_name="Zug").fights[0]
        other = fight.actor_by_name("Other")
        assert other is not None
        assert fight.timeline_for(other.id) is None

        # New adapter calls fire exactly once — only for the target character.
        assert fake.call_counts.get("cast_events") == 1
        assert fake.call_counts.get("damage_graph") == 1
