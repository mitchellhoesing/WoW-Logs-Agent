You are reviewing two World of Warcraft combat-log runs for the same player on the
same encounter. The player wants a prioritized, specific list of changes that would
lift the lower-DPS run toward the higher-DPS one.

## Input

- **Encounter:** $encounter
- **Player:** $actor ($class_spec)

The JSON below contains the full comparison. `higher_dps_run` is the run with higher
DPS; `lower_dps_run` is the run the player wants to improve. `top_ability_deltas` is
already sorted by absolute DPS-contribution impact; each row has `higher_dps_run` and
`lower_dps_run` sides carrying that ability's casts, damage, uptime, and contribution.

When present, `timelines` holds per-run timing data for the same player:
- `cooldown_casts[]` — each cast with `offset_s` (seconds from pull start), `ability_id`, and `ability_name`.
- `buff_windows[]` — self-buff coverage with `start_s`, `end_s`, `duration_s`, and the ability.
- `dps_buckets[]` — fixed-width DPS samples with `start_s`, `end_s`, and `dps`.

Use timelines to reason about *when* things happened (late trinkets, held CDs, coverage
gaps, lulls that coincide with missing buffs). If the `timelines` key is absent from the
JSON, skip all timing analysis — do not fabricate offsets.

```json
$context_json
```

## Output

Produce a markdown response with exactly these sections:

1. **Headline** — one sentence: the single biggest behavioral difference.
2. **Top findings** — 3 to 6 numbered findings, each:
   - Name the ability or mechanic.
   - Quote the specific numbers from the JSON (casts, uptime %, DPS contribution).
   - Explain in one or two sentences what the player likely did differently.
   - End with an imperative "Next pull:" action.
3. **Timing observations** *(include only if `timelines` is present)* — 1 to 3
   bullets drawn from `cooldown_casts`, `buff_windows`, or `dps_buckets`. Quote
   concrete offsets in seconds. Omit this section entirely when `timelines` is
   absent from the JSON.
4. **Sanity checks** — 1 to 3 bullets flagging anything suspicious in the data
   (e.g. fight duration delta large enough to explain DPS change on its own, an
   ability present in one run but absent from the other).
5. **What not to change** — 1 to 3 bullets calling out things the player did well
   in the lower-DPS run that should be preserved.

Rules:

- Do not invent abilities, numbers, mechanics, or timestamps that are not in the JSON.
- Prefer percentages and counts over vague adjectives.
- Keep the whole response under ~1000 words.
