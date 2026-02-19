"""Project capability summary reader for EA (D59).

EA reads per-project capability data from ProjectRegistry to make informed
routing decisions without full plugin awareness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProjectCapability:
    """Capability summary for a single project.

    :param name: Project name.
    :param plugin: Plugin type (e.g. "software", "documents").
    :param ci_signals: Available CI signal types.
    :param done_definition: Human-readable definition of "done".
    :param critical_tools: Tools essential for this project type.
    :param autonomy_stage: Current autonomy level.
    """

    name: str
    plugin: str = "software"
    ci_signals: list[str] = field(default_factory=list)
    done_definition: str = ""
    critical_tools: list[str] = field(default_factory=list)
    autonomy_stage: str = "supervised"


PLUGIN_DEFAULTS: dict[str, dict[str, Any]] = {
    "software": {
        "ci_signals": ["pytest", "ruff", "pyright"],
        "done_definition": "All tests pass, lint clean, type check clean",
        "critical_tools": ["bash", "git", "run_tests"],
    },
    "documents": {
        "ci_signals": ["link_check", "structure_validation"],
        "done_definition": "Links valid, structure verified, preview rendered",
        "critical_tools": ["read_file", "write_file", "glob"],
    },
}


def build_capability(
    *,
    name: str,
    plugin: str = "software",
    local_path: str = "",
    autonomy_stage: str = "supervised",
    overrides: dict[str, Any] | None = None,
) -> ProjectCapability:
    """Build a capability summary for a project.

    Uses plugin defaults as base, applies any overrides.

    :param name: Project name.
    :param plugin: Plugin type.
    :param local_path: Project local path (unused currently, reserved).
    :param autonomy_stage: Autonomy stage string.
    :param overrides: Optional dict to override default fields.
    :returns: ProjectCapability instance.
    """
    defaults = PLUGIN_DEFAULTS.get(plugin, {})
    merged = {**defaults, **(overrides or {})}

    return ProjectCapability(
        name=name,
        plugin=plugin,
        ci_signals=merged.get("ci_signals", []),
        done_definition=merged.get("done_definition", ""),
        critical_tools=merged.get("critical_tools", []),
        autonomy_stage=autonomy_stage,
    )


def format_capabilities_for_prompt(capabilities: list[ProjectCapability]) -> str:
    """Format project capabilities as text for the EA system prompt.

    :param capabilities: List of project capability summaries.
    :returns: Formatted text suitable for inclusion in system prompt.
    """
    if not capabilities:
        return "No projects registered."

    lines: list[str] = []
    for cap in capabilities:
        lines.append(f"### {cap.name}")
        lines.append(f"- Plugin: {cap.plugin}")
        if cap.ci_signals:
            lines.append(f"- CI signals: {', '.join(cap.ci_signals)}")
        if cap.done_definition:
            lines.append(f"- Done when: {cap.done_definition}")
        if cap.critical_tools:
            lines.append(f"- Critical tools: {', '.join(cap.critical_tools)}")
        lines.append(f"- Autonomy: {cap.autonomy_stage}")
        lines.append("")

    return "\n".join(lines)
