from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, ClassVar

from wowlogs_agent.domain.entities import (
    AbilityUsage,
    Actor,
    ActorRole,
    CombatEvent,
    CombatLog,
    Fight,
)
from wowlogs_agent.domain.ports.combat_log_repository import CombatLogRepository
from wowlogs_agent.domain.value_objects import DPS, BuffWindow, DpsBucket, TimeWindow, Timeline
from wowlogs_agent.gateways.warcraft_logs.graphql_client import WarcraftLogsGraphQLClient
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
from wowlogs_agent.services.timeline_builder import TimelineBuilder


@dataclass(frozen=True)
class _PlayerEnrichment:
    spec: str | None
    role: ActorRole | None
    class_name: str | None
    item_level: float | None


@dataclass(frozen=True)
class _AbilityDamage:
    name: str
    total_damage: int
    hit_count: int


class GraphQLCombatLogRepository(CombatLogRepository):
    """Fetches a report and builds the domain aggregate with a full per-ability
    breakdown for the compared character.

    Only the target character's usages are compared downstream, so expensive
    per-ability queries are scoped to that actor. The default summary DamageDone
    table truncates each actor's `abilities` subfield to the top-N rows — that
    silently drops abilities sitting outside one side's top-5 but inside the
    other's, producing a false "absent in log A" signal. Pivoting by Ability
    with `sourceID` returns one entry per ability with no truncation.

    Uptime source: the WCL Buffs table is queried once per (fight, target player).
    Each entry's `totalUptime` is in milliseconds across the fight; we map it by
    ability `guid` to the corresponding AbilityUsage. Abilities that do not produce
    an aura (e.g. instant damage spells) naturally have no buff-table entry and
    retain `active_seconds=0.0`.
    """

    _PLAYER_ROLES: ClassVar[dict[str, ActorRole]] = {
        "Tank": ActorRole.TANK,
        "Healer": ActorRole.HEALER,
        "DPS": ActorRole.DPS,
    }

    def __init__(
        self,
        client: WarcraftLogsGraphQLClient,
        timeline_builder: TimelineBuilder | None = None,
    ) -> None:
        self._client = client
        self._timeline_builder = timeline_builder or TimelineBuilder()

    def fetch(
        self,
        report_id: str,
        *,
        fight_id: int | None = None,
        character_name: str | None = None,
    ) -> CombatLog:
        summary = self._client.execute(
            REPORT_SUMMARY_QUERY,
            {"code": report_id},
            cache_namespace=f"{report_id}/summary",
        )
        report = summary["data"]["reportData"]["report"]
        actors = self._parse_actors(report)
        raw_fights = report["fights"]
        if fight_id is not None:
            raw_fights = [f for f in raw_fights if int(f.get("id") or 0) == fight_id]
        fights = tuple(
            self._fetch_fight(report_id, raw_fight, actors, character_name)
            for raw_fight in raw_fights
        )

        return CombatLog(
            report_id=report["code"],
            title=report.get("title") or "",
            owner=(report.get("owner") or {}).get("name") or "",
            start_unix_ms=int(report.get("startTime") or 0),
            zone_name=(report.get("zone") or {}).get("name") or "",
            fights=fights,
        )

    # ---- helpers -----------------------------------------------------------------

    def _parse_actors(self, report: Mapping[str, Any]) -> dict[int, Actor]:
        master = report.get("masterData") or {}
        enrichments = self._parse_player_details(report.get("playerDetails"))

        actors: dict[int, Actor] = {}
        for raw in master.get("actors") or []:
            actor_id = int(raw["id"])
            class_name, spec_name = self._class_spec_from_actor(raw)
            role = ActorRole.DPS
            item_level: float | None = None

            enrichment = enrichments.get(actor_id)
            if enrichment is not None:
                if enrichment.spec:
                    spec_name = enrichment.spec
                if enrichment.role is not None:
                    role = enrichment.role
                if enrichment.class_name:
                    class_name = enrichment.class_name
                item_level = enrichment.item_level

            actors[actor_id] = Actor(
                id=actor_id,
                name=str(raw.get("name") or f"actor:{actor_id}"),
                role=role,
                class_name=class_name,
                spec_name=spec_name,
                item_level=item_level,
            )
        return actors

    @staticmethod
    def _parse_player_details(raw: Any) -> dict[int, _PlayerEnrichment]:
        """Flatten WCL's `playerDetails` JSON into `{actor_id: enrichment}`.

        The payload wraps its role buckets under `data`: `{"data": {"dps": [...],
        "healers": [...], "tanks": [...]}}`. Each player carries a `specs` list
        whose first entry holds the dominant spec/role for the filtered fights.
        """
        if not isinstance(raw, Mapping):
            return {}
        # WCL wraps the payload as `{"data": {"playerDetails": {"dps": [...], ...}}}`.
        # Peel both layers while tolerating either being absent in tests.
        buckets: Mapping[str, Any] = raw
        inner = buckets.get("data")
        if isinstance(inner, Mapping):
            buckets = inner
        inner = buckets.get("playerDetails")
        if isinstance(inner, Mapping):
            buckets = inner

        role_by_bucket: Mapping[str, ActorRole] = {
            "dps": ActorRole.DPS,
            "healers": ActorRole.HEALER,
            "tanks": ActorRole.TANK,
        }
        result: dict[int, _PlayerEnrichment] = {}
        for bucket, bucket_role in role_by_bucket.items():
            for entry in buckets.get(bucket) or []:
                if not isinstance(entry, Mapping):
                    continue
                actor_id = int(entry.get("id") or 0)
                if not actor_id:
                    continue
                specs = entry.get("specs") or []
                spec: str | None = None
                spec_role: ActorRole | None = bucket_role
                # WCL's `specs` is a list of {spec, role, count} — unsorted.
                # Pick the entry with the highest `count` so off-spec fights
                # don't mislabel a player who played their main in most pulls.
                dominant: Mapping[str, Any] | None = None
                best_count = -1
                for candidate in specs:
                    if not isinstance(candidate, Mapping):
                        continue
                    count = candidate.get("count")
                    count_int = int(count) if isinstance(count, (int, float)) else 0
                    if count_int > best_count:
                        best_count = count_int
                        dominant = candidate
                if dominant is not None:
                    spec_value = dominant.get("spec")
                    if isinstance(spec_value, str) and spec_value:
                        spec = spec_value
                    role_value = dominant.get("role")
                    if isinstance(role_value, str):
                        mapped = role_by_bucket.get(role_value.lower() + "s")
                        if mapped is not None:
                            spec_role = mapped
                class_name_raw = entry.get("type")
                class_name = str(class_name_raw) if isinstance(class_name_raw, str) else None
                ilvl_raw = entry.get("minItemLevel") or entry.get("maxItemLevel")
                item_level = float(ilvl_raw) if isinstance(ilvl_raw, (int, float)) else None
                result[actor_id] = _PlayerEnrichment(
                    spec=spec,
                    role=spec_role,
                    class_name=class_name,
                    item_level=item_level,
                )
        return result

    @staticmethod
    def _class_spec_from_actor(raw: Mapping[str, Any]) -> tuple[str | None, str | None]:
        """Extract (class, spec) from a WCL masterData actor.

        WCL `icon` for players is formatted `"ClassName-SpecName"` (e.g.
        `"Warrior-Arms"`). `subType` carries the class reliably; `icon` is the
        only source of spec in this query shape. Falls back to None on either
        side when the data is absent or malformed.
        """
        subtype = raw.get("subType")
        class_name = str(subtype) if subtype else None

        icon = raw.get("icon")
        spec_name: str | None = None
        if isinstance(icon, str) and "-" in icon:
            icon_class, _, icon_spec = icon.partition("-")
            if icon_spec:
                spec_name = icon_spec
                if class_name is None and icon_class:
                    class_name = icon_class
        return class_name, spec_name

    def _fetch_fight(
        self,
        report_id: str,
        raw_fight: Mapping[str, Any],
        actors_by_id: Mapping[int, Actor],
        character_name: str | None = None,
    ) -> Fight:
        fight_id = int(raw_fight["id"])
        start_ms = int(raw_fight["startTime"])
        end_ms = int(raw_fight["endTime"])
        window = TimeWindow(start_ms=0, end_ms=max(1, end_ms - start_ms))
        duration_s = window.duration_seconds

        damage_summary = self._client.execute(
            FIGHT_DAMAGE_TABLE_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-damage",
        )
        summary_table = damage_summary["data"]["reportData"]["report"]["table"]
        summary_entries = (summary_table.get("data") or {}).get("entries") or []

        fight_enrichments = self._fetch_fight_player_details(
            report_id, fight_id, start_ms, end_ms
        )

        target_lower = character_name.lower() if character_name else None
        friendly_ids = [int(pid) for pid in (raw_fight.get("friendlyPlayers") or [])]
        present_actors: list[Actor] = []
        usages_by_actor: dict[int, tuple[AbilityUsage, ...]] = {}
        damage_by_actor: dict[int, int] = {}
        timelines_by_actor: dict[int, Timeline] = {}

        for entry in summary_entries:
            actor_id = int(entry.get("id") or 0)
            if actor_id not in actors_by_id:
                continue
            actor = self._apply_fight_enrichment(
                actors_by_id[actor_id], fight_enrichments.get(actor_id)
            )
            present_actors.append(actor)
            damage_by_actor[actor_id] = int(entry.get("total") or 0)

            # Per-ability breakdowns, buff uptime, and the timeline are only
            # consumed for the compared character. Scoping these to the target
            # cuts the bulk of the API traffic on a busy raid-night report and —
            # critically — avoids the top-N truncation of the unscoped summary
            # table.
            if target_lower is None or actor.name.lower() != target_lower:
                usages_by_actor[actor_id] = ()
                continue

            damage_by_ability = self._fetch_actor_ability_damage(
                report_id, fight_id, start_ms, end_ms, actor_id
            )
            casts_by_ability = self._fetch_actor_ability_casts(
                report_id, fight_id, start_ms, end_ms, actor_id
            )
            # One buff-table fetch feeds two parsers: aggregate uptime (for
            # AbilityUsage) and per-activation bands (for the timeline).
            buffs_response = self._fetch_buff_table(
                report_id, fight_id, start_ms, end_ms, actor_id
            )
            uptime_by_ability = self._parse_buff_uptime_seconds(buffs_response)
            buff_windows = self._extract_buff_bands(buffs_response, start_ms)

            usages = self._build_usages(
                damage_by_ability=damage_by_ability,
                casts_by_ability=casts_by_ability,
                uptime_by_ability=uptime_by_ability,
                fight_duration_s=duration_s,
            )
            usages_by_actor[actor_id] = usages

            cast_events = self._fetch_fight_cast_events(
                report_id, fight_id, start_ms, end_ms, actor_id
            )
            dps_buckets = self._fetch_fight_damage_graph(
                report_id, fight_id, start_ms, end_ms, actor_id
            )
            timelines_by_actor[actor_id] = self._timeline_builder.build(
                cast_events=cast_events,
                buff_windows=buff_windows,
                dps_buckets=dps_buckets,
                ability_name_by_id={u.ability_id: u.name for u in usages},
            )

        present_ids = {a.id for a in present_actors}
        for pid in friendly_ids:
            if pid in actors_by_id and pid not in present_ids:
                present_actors.append(
                    self._apply_fight_enrichment(
                        actors_by_id[pid], fight_enrichments.get(pid)
                    )
                )
                present_ids.add(pid)

        return Fight(
            id=fight_id,
            encounter_id=int(raw_fight.get("encounterID") or 0),
            encounter_name=str(raw_fight.get("name") or ""),
            window=window,
            kill=bool(raw_fight.get("kill")),
            difficulty=int(raw_fight.get("difficulty") or 0),
            actors=tuple(present_actors),
            ability_usages=MappingProxyType(usages_by_actor),
            damage_by_actor=MappingProxyType(damage_by_actor),
            timelines=MappingProxyType(timelines_by_actor),
        )

    @staticmethod
    def _build_usages(
        *,
        damage_by_ability: Mapping[int, _AbilityDamage],
        casts_by_ability: Mapping[int, int],
        uptime_by_ability: Mapping[int, float],
        fight_duration_s: float,
    ) -> tuple[AbilityUsage, ...]:
        """Merge the three per-ability streams keyed by ability_id.

        Union ability ids across damage and casts tables: a player can cast an
        ability that never lands damage (missed, absorbed, dispelled), and pets
        do damage the player never cast directly. We want both sides represented
        in the comparison so an ability cast zero times on one run but many on
        the other shows up in the delta.
        """
        ability_ids = set(damage_by_ability) | set(casts_by_ability)
        usages: list[AbilityUsage] = []
        for ability_id in ability_ids:
            dmg = damage_by_ability.get(ability_id)
            casts = casts_by_ability.get(ability_id, 0)
            name = dmg.name if dmg else f"ability:{ability_id}"
            total_damage = dmg.total_damage if dmg else 0
            hit_count = dmg.hit_count if dmg else 0
            usages.append(
                AbilityUsage(
                    ability_id=ability_id,
                    name=name,
                    casts=casts,
                    hits=hit_count,
                    total_damage=total_damage,
                    active_seconds=min(
                        fight_duration_s, uptime_by_ability.get(ability_id, 0.0)
                    ),
                    fight_duration_seconds=fight_duration_s,
                )
            )
        return tuple(usages)

    def _fetch_actor_ability_damage(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
        actor_id: int,
    ) -> dict[int, _AbilityDamage]:
        """Return `{ability_id: _AbilityDamage}` for damage done by `actor_id`.

        Uses `viewBy: Ability` + `sourceID` to sidestep the top-N truncation of
        the default per-source view. The response's `entries` is one row per
        ability (not per actor).
        """
        response = self._client.execute(
            FIGHT_ACTOR_DAMAGE_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
                "sourceID": actor_id,
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-damage-by-ability-{actor_id}",
        )
        table = response["data"]["reportData"]["report"]["table"]
        entries = (table.get("data") or {}).get("entries") or []
        result: dict[int, _AbilityDamage] = {}
        for entry in entries:
            ability_id = int(entry.get("guid") or entry.get("id") or 0)
            if not ability_id:
                continue
            result[ability_id] = _AbilityDamage(
                name=str(entry.get("name") or f"ability:{ability_id}"),
                total_damage=int(entry.get("total") or 0),
                hit_count=int(entry.get("hitCount") or 0),
            )
        return result

    def _fetch_actor_ability_casts(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
        actor_id: int,
    ) -> dict[int, int]:
        """Return `{ability_id: cast_count}` for casts by `actor_id`.

        Pivoted by Ability to mirror the damage query shape. In the Casts table
        the `total` field of each ability-pivoted entry is the cast count.
        """
        response = self._client.execute(
            FIGHT_ACTOR_CASTS_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
                "sourceID": actor_id,
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-casts-by-ability-{actor_id}",
        )
        table = response["data"]["reportData"]["report"]["table"]
        entries = (table.get("data") or {}).get("entries") or []
        result: dict[int, int] = {}
        for entry in entries:
            ability_id = int(entry.get("guid") or entry.get("id") or 0)
            if not ability_id:
                continue
            result[ability_id] = int(entry.get("total") or 0)
        return result

    def _fetch_fight_player_details(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
    ) -> dict[int, _PlayerEnrichment]:
        """Return per-fight enrichments keyed by actor id.

        A player who swapped specs between pulls will have a different dominant
        spec in the report-level payload than in the specific fight being
        compared. Querying playerDetails scoped to this fight's ids gives the
        spec/role the player actually used for this pull.
        """
        response = self._client.execute(
            FIGHT_PLAYER_DETAILS_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-players",
        )
        report = response["data"]["reportData"]["report"]
        return self._parse_player_details(report.get("playerDetails"))

    @staticmethod
    def _apply_fight_enrichment(
        actor: Actor, enrichment: _PlayerEnrichment | None
    ) -> Actor:
        if enrichment is None:
            return actor
        return replace(
            actor,
            class_name=enrichment.class_name or actor.class_name,
            spec_name=enrichment.spec or actor.spec_name,
            role=enrichment.role if enrichment.role is not None else actor.role,
            item_level=enrichment.item_level
            if enrichment.item_level is not None
            else actor.item_level,
        )

    def _fetch_buff_table(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
        actor_id: int,
    ) -> Mapping[str, Any]:
        """Fetch the per-(fight, actor) Buffs table response. Cached on disk,
        so both the uptime parser and the band parser read the same bytes."""
        return self._client.execute(
            FIGHT_BUFF_TABLE_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
                "targetID": actor_id,
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-buffs-{actor_id}",
        )

    @staticmethod
    def _buff_table_entries(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        table = response["data"]["reportData"]["report"]["table"]
        data = table.get("data") or {}
        raw = data.get("auras") or data.get("entries") or []
        return [e for e in raw if isinstance(e, Mapping)]

    @classmethod
    def _parse_buff_uptime_seconds(
        cls, response: Mapping[str, Any]
    ) -> dict[int, float]:
        """Extract `{ability_id: active_seconds}` from a cached Buffs response."""
        uptime_ms_by_ability: dict[int, int] = {}
        for entry in cls._buff_table_entries(response):
            ability_id = int(entry.get("guid") or entry.get("id") or 0)
            if not ability_id:
                continue
            uptime_ms = int(entry.get("totalUptime") or 0)
            # Take the max across duplicate entries (same buff from multiple sources).
            prev = uptime_ms_by_ability.get(ability_id, 0)
            if uptime_ms > prev:
                uptime_ms_by_ability[ability_id] = uptime_ms
        return {aid: ms / 1000.0 for aid, ms in uptime_ms_by_ability.items()}

    @classmethod
    def _extract_buff_bands(
        cls, response: Mapping[str, Any], fight_start_abs_ms: int
    ) -> tuple[BuffWindow, ...]:
        """Parse per-activation buff windows out of the Buffs response.

        WCL returns absolute timestamps in `bands[].startTime/endTime`; the
        domain uses fight-relative ms, so subtract `fight_start_abs_ms`. Windows
        that land fully before the fight (clock skew / early auras) are dropped.
        """
        windows: list[BuffWindow] = []
        for entry in cls._buff_table_entries(response):
            ability_id = int(entry.get("guid") or entry.get("id") or 0)
            if not ability_id:
                continue
            name = str(entry.get("name") or f"ability:{ability_id}")
            raw_bands = entry.get("bands") or []
            for band in raw_bands:
                if not isinstance(band, Mapping):
                    continue
                start_abs = int(band.get("startTime") or 0)
                end_abs = int(band.get("endTime") or 0)
                start_rel = max(0, start_abs - fight_start_abs_ms)
                end_rel = end_abs - fight_start_abs_ms
                if end_rel <= start_rel:
                    continue
                windows.append(
                    BuffWindow(
                        start_ms=start_rel,
                        end_ms=end_rel,
                        ability_id=ability_id,
                        ability_name=name,
                    )
                )
        return tuple(windows)

    def _fetch_fight_cast_events(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
        actor_id: int,
    ) -> tuple[CombatEvent, ...]:
        """Paginate over `events(dataType: Casts)` until `nextPageTimestamp` is null.

        The loop usually terminates after one iteration — one player's casts on
        a 10-minute pull fit comfortably in a single 10_000-row page. Each page
        is cached independently because `$start` differs, so a re-run costs zero
        HTTP traffic.
        """
        events: list[CombatEvent] = []
        cursor = float(start_ms)
        seen_cursors: set[float] = set()
        while True:
            if cursor in seen_cursors:
                # Defensive: guard against a WCL bug where nextPageTimestamp
                # equals the current start — would otherwise loop forever.
                break
            seen_cursors.add(cursor)

            response = self._client.execute(
                FIGHT_CAST_EVENTS_QUERY,
                {
                    "code": report_id,
                    "fightID": fight_id,
                    "start": cursor,
                    "end": float(end_ms),
                    "sourceID": actor_id,
                },
                cache_namespace=f"{report_id}/fight-{fight_id}-casts-{actor_id}",
            )
            payload = (
                response["data"]["reportData"]["report"].get("events") or {}
            )
            for raw in payload.get("data") or []:
                if not isinstance(raw, Mapping):
                    continue
                ability_id = int(
                    raw.get("abilityGameID")
                    or (raw.get("ability") or {}).get("guid")
                    or 0
                )
                source_id = int(raw.get("sourceID") or 0)
                timestamp_abs = int(raw.get("timestamp") or 0)
                if not ability_id or not source_id:
                    continue
                target_raw = raw.get("targetID")
                target_id = int(target_raw) if isinstance(target_raw, (int, float)) else None
                events.append(
                    CombatEvent(
                        timestamp_ms=max(0, timestamp_abs - start_ms),
                        ability_id=ability_id,
                        source_id=source_id,
                        target_id=target_id,
                    )
                )

            next_ts = payload.get("nextPageTimestamp")
            if not isinstance(next_ts, (int, float)):
                break
            cursor = float(next_ts)
        return tuple(events)

    def _fetch_fight_damage_graph(
        self,
        report_id: str,
        fight_id: int,
        start_ms: int,
        end_ms: int,
        actor_id: int,
    ) -> tuple[DpsBucket, ...]:
        """Fetch WCL's pre-bucketed damage-done graph for one actor.

        The `graph` field returns a JSON scalar whose exact shape has varied
        across WCL schema versions. We tolerate both `{data: {series: [...] }}`
        and bare `{series: [...]}` envelopes, and both `[x, y]` pairs and
        `{x, y}` point objects. Timestamps are normalized to fight-relative:
        if x looks absolute (>= fight_start_abs) we subtract; if already small,
        we treat it as relative.
        """
        response = self._client.execute(
            FIGHT_DAMAGE_GRAPH_QUERY,
            {
                "code": report_id,
                "fightID": fight_id,
                "start": float(start_ms),
                "end": float(end_ms),
                "sourceID": actor_id,
            },
            cache_namespace=f"{report_id}/fight-{fight_id}-dps-graph-{actor_id}",
        )
        raw_graph = response["data"]["reportData"]["report"].get("graph") or {}
        envelope = raw_graph.get("data") if isinstance(raw_graph.get("data"), Mapping) else raw_graph
        if not isinstance(envelope, Mapping):
            return ()
        series_list = envelope.get("series") or []
        if not series_list:
            return ()
        series = series_list[0] if isinstance(series_list[0], Mapping) else {}
        point_interval = int(envelope.get("pointInterval") or series.get("pointInterval") or 0)
        if point_interval <= 0:
            # Fall back to a sensible default bucket width so downstream code
            # still gets windowed data.
            point_interval = 10_000
        points = series.get("data") or []
        buckets: list[DpsBucket] = []
        for point in points:
            x, y = self._unpack_graph_point(point)
            if x is None or y is None:
                continue
            rel = int(x - start_ms) if x >= start_ms else int(x)
            if rel < 0:
                rel = 0
            bucket_start = rel
            bucket_end = rel + point_interval
            seconds = point_interval / 1000.0
            # Graph values for DamageDone are per-bucket totals in most WCL
            # schema variants; converting to DPS keeps the value object honest.
            dps_value = max(0.0, float(y) / seconds)
            buckets.append(
                DpsBucket(
                    start_ms=bucket_start,
                    end_ms=bucket_end,
                    dps=DPS(dps_value),
                )
            )
        return tuple(buckets)

    @staticmethod
    def _unpack_graph_point(point: Any) -> tuple[float | None, float | None]:
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            x_raw, y_raw = point[0], point[1]
        elif isinstance(point, Mapping):
            x_raw = point.get("x") or point.get("time") or point.get("timestamp")
            y_raw = point.get("y") or point.get("value") or point.get("total")
        else:
            return None, None
        if not isinstance(x_raw, (int, float)) or not isinstance(y_raw, (int, float)):
            return None, None
        return float(x_raw), float(y_raw)
