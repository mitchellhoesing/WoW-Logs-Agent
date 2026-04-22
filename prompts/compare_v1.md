You are reviewing two World of Warcraft combat-log runs for the same player on the
same encounter. The player wants a prioritized, specific list of changes that would
lift the worse run toward the better one.

## Input

- **Encounter:** $encounter
- **Player:** $actor ($class_spec)

The JSON below contains the full comparison. `better` is the higher-DPS run, `worse`
is the run the player wants to improve. `top_ability_deltas` is already sorted by
absolute DPS-contribution impact.

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
3. **Sanity checks** — 1 to 3 bullets flagging anything suspicious in the data
   (e.g. fight duration delta large enough to explain DPS change on its own, an
   ability present in one run but absent from the other).
4. **What not to change** — 1 to 3 bullets calling out things the player did well
   in the worse run that should be preserved.

Rules:

- Do not invent abilities, numbers, or mechanics that are not in the JSON.
- Prefer percentages and counts over vague adjectives.
- Keep the whole response under ~1000 words.
