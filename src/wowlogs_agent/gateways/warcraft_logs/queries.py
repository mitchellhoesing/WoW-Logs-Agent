"""GraphQL query constants for the WarcraftLogs v2 API.

Kept as string constants so they can be hashed and cached by content.
"""

from __future__ import annotations

REPORT_SUMMARY_QUERY = """
query ReportSummary($code: String!) {
  reportData {
    report(code: $code) {
      code
      title
      owner { name }
      startTime
      zone { name }
      fights(killType: Encounters) {
        id
        encounterID
        name
        startTime
        endTime
        kill
        difficulty
        friendlyPlayers
      }
      masterData(translate: true) {
        actors(type: "Player") {
          id
          name
          type
          subType
          icon
        }
        abilities { gameID name }
      }
      playerDetails(killType: Encounters, startTime: 0, endTime: 999999999999)
    }
  }
}
""".strip()


FIGHT_PLAYER_DETAILS_QUERY = """
query FightPlayerDetails(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!
) {
  reportData {
    report(code: $code) {
      playerDetails(fightIDs: [$fightID], startTime: $start, endTime: $end)
    }
  }
}
""".strip()


FIGHT_DAMAGE_TABLE_QUERY = """
query FightDamage($code: String!, $fightID: Int!, $start: Float!, $end: Float!) {
  reportData {
    report(code: $code) {
      table(
        dataType: DamageDone,
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end
      )
    }
  }
}
""".strip()


# The default `viewBy: Source` table truncates each actor's `abilities` subfield
# to the top N rows, which silently drops abilities from the comparison (e.g.
# Hand of Gul'dan present for one warlock but outside the other's top-5).
# Pivoting by Ability with `sourceID` gives one entry per ability used by that
# source with no truncation.
FIGHT_ACTOR_DAMAGE_QUERY = """
query FightActorDamage(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!,
  $sourceID: Int!
) {
  reportData {
    report(code: $code) {
      table(
        dataType: DamageDone,
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end,
        sourceID: $sourceID,
        viewBy: Ability
      )
    }
  }
}
""".strip()


FIGHT_ACTOR_CASTS_QUERY = """
query FightActorCasts(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!,
  $sourceID: Int!
) {
  reportData {
    report(code: $code) {
      table(
        dataType: Casts,
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end,
        sourceID: $sourceID,
        viewBy: Ability
      )
    }
  }
}
""".strip()


FIGHT_BUFF_TABLE_QUERY = """
query FightBuffs(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!,
  $targetID: Int!
) {
  reportData {
    report(code: $code) {
      table(
        dataType: Buffs,
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end,
        hostilityType: Friendlies,
        targetID: $targetID
      )
    }
  }
}
""".strip()


# Cast events only — the rest of the timeline is derived from the existing Buffs
# table (aura bands) and the pre-aggregated damage graph. Filtering to `Casts`
# keeps one player's response to ~100-300 rows, virtually always a single page.
# The pagination loop in the repository advances `$start` to the previous page's
# `nextPageTimestamp` each iteration; WCL's `events` field has no separate
# cursor variable — `startTime` doubles as the cursor.
FIGHT_CAST_EVENTS_QUERY = """
query FightCastEvents(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!,
  $sourceID: Int!
) {
  reportData {
    report(code: $code) {
      events(
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end,
        sourceID: $sourceID,
        dataType: Casts,
        limit: 10000
      ) {
        data
        nextPageTimestamp
      }
    }
  }
}
""".strip()


# Pre-aggregated damage-done-over-time. Single response (no pagination). Returns
# an opaque JSON scalar whose shape the gateway parses defensively — see
# GraphQLCombatLogRepository._fetch_fight_damage_graph.
FIGHT_DAMAGE_GRAPH_QUERY = """
query FightDamageGraph(
  $code: String!,
  $fightID: Int!,
  $start: Float!,
  $end: Float!,
  $sourceID: Int!
) {
  reportData {
    report(code: $code) {
      graph(
        dataType: DamageDone,
        fightIDs: [$fightID],
        startTime: $start,
        endTime: $end,
        sourceID: $sourceID
      )
    }
  }
}
""".strip()
