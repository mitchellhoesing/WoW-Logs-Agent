You are reviewing two World of Warcraft combat-log runs on the same encounter.
The goal is a prioritized, specific list of changes that would lift the lower-DPS
run toward the higher-DPS one.

## Input

- **Encounter:** $encounter
- **Higher-DPS run:** $higher_character ($higher_class_spec)
- **Lower-DPS run:** $lower_character ($lower_class_spec)

The two sides may be the same player on two different pulls, or two different
players in the same class/spec. Treat them as comparable only if the class and
spec match; if they differ, say so in **Sanity checks** and scope advice
accordingly.

The JSON below contains the full comparison. Each of `fights.higher_dps_run` and
`fights.lower_dps_run` carries its own `character` block (name, class/spec, role,
item level). `top_ability_deltas` is already sorted by absolute DPS-contribution
impact; each row has `higher_dps_run` and `lower_dps_run` sides carrying that
ability's casts, damage, uptime, and contribution.

```json
$context_json
```

## Output

Produce a markdown response with exactly these sections:

1. **Headline** — one sentence: the single biggest behavioral difference.
2. **Top findings** — 3 to 6 numbered findings, each:
   - Name the ability or mechanic.
   - Quote the specific numbers from the JSON (casts, uptime %, DPS contribution).
   - Explain in one or two sentences what the player likely did differently (spell usage, cooldown usage, buff overlaps, cooldown timings).
   - End with an imperative "Next pull:" action.
3. **Sanity checks** — 1 to 3 bullets flagging anything suspicious in the data
   (e.g. class/spec mismatch between the two sides, fight duration delta large
   enough to explain DPS change on its own, an ability present in one run but
   absent from the other).
4. **What not to change** — 1 to 3 bullets calling out things the lower-DPS run
   did well that should be preserved.

Rules:

- Do not invent abilities, numbers, or mechanics that are not in the JSON.
- Prefer percentages and counts over vague adjectives.
- Keep the whole response under ~1000 words.
