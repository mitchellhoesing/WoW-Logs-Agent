from __future__ import annotations

from wowlogs_agent.domain.performance import PerformanceDelta
from wowlogs_agent.domain.ports.report_renderer import ReportRenderer


class MarkdownReportRenderer(ReportRenderer):
    """Renders a delta + LLM analysis into a markdown document for terminal or file."""

    def render(self, delta: PerformanceDelta, llm_analysis: str) -> str:
        higher = delta.higher
        lower = delta.lower
        actor = higher.actor

        lines: list[str] = []
        lines.append(f"# {actor.name} — {higher.encounter_name}")
        lines.append("")
        lines.append(f"**Spec:** {actor.class_spec}  ")
        lines.append(f"**Role:** {actor.role.value}  ")
        lines.append("")
        lines.append("## Summary")
        lines.append("")
        lines.append("| Metric | Higher-DPS run | Lower-DPS run | Δ |")
        lines.append("|---|---:|---:|---:|")
        lines.append(
            f"| Report | `{higher.report_id}` / fight {higher.fight_id} "
            f"| `{lower.report_id}` / fight {lower.fight_id} | |"
        )
        lines.append(
            f"| DPS | {higher.dps.value:,.0f} | {lower.dps.value:,.0f} "
            f"| {delta.dps_delta:+,.0f} ({delta.dps_pct_change*100:+.1f}%) |"
        )
        lines.append(
            f"| Duration (s) | {higher.duration_seconds:.1f} | {lower.duration_seconds:.1f} "
            f"| {delta.duration_delta_seconds:+.1f} |"
        )
        lines.append("")
        lines.append("## Top ability deltas")
        lines.append("")
        lines.append("| Ability | Casts Δ | Damage Δ | Uptime Δ | DPS-contribution Δ |")
        lines.append("|---|---:|---:|---:|---:|")
        for row in delta.top_ability_deltas(10):
            lines.append(
                f"| {row.name} | {row.casts_delta:+d} | {row.damage_delta:+,d} "
                f"| {row.uptime_delta*100:+.1f}% | {row.dps_contribution_delta:+,.0f} |"
            )
        lines.append("")
        lines.append("## Coaching recommendations")
        lines.append("")
        lines.append(llm_analysis.strip())
        lines.append("")
        return "\n".join(lines)
