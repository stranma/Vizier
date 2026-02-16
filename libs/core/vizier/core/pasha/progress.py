"""Progress reporting: status.json, cycle reports, escalations."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ProjectStatus(BaseModel):
    """Current project status for status.json.

    :param project: Project name.
    :param timestamp: When this status was generated.
    :param total_specs: Total number of specs.
    :param by_status: Count of specs per status.
    :param active_agents: Number of currently running agents.
    :param cycle_count: Total completed orchestration cycles.
    """

    project: str = ""
    timestamp: str = ""
    total_specs: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    active_agents: int = 0
    cycle_count: int = 0


class CycleReport(BaseModel):
    """A single orchestration cycle report.

    :param cycle: Cycle number.
    :param timestamp: When the cycle completed.
    :param specs_processed: Specs that changed state during this cycle.
    :param agents_spawned: Agents launched during this cycle.
    :param errors: Any errors encountered.
    """

    cycle: int = 0
    timestamp: str = ""
    specs_processed: list[str] = Field(default_factory=list)
    agents_spawned: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ProgressReporter:
    """Writes progress reports to the reports/ directory.

    :param reports_dir: Path to the reports directory (e.g. reports/project-name/).
    """

    def __init__(self, reports_dir: str | Path) -> None:
        self._dir = Path(reports_dir)

    def write_status(self, status: ProjectStatus) -> str:
        """Write status.json to reports directory.

        :param status: Current project status.
        :returns: Path to the written file.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / "status.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(status.model_dump(), indent=2, default=str), encoding="utf-8")
        os.replace(str(tmp), str(path))
        return str(path)

    def write_cycle_report(self, report: CycleReport) -> str:
        """Write a cycle report markdown file.

        :param report: The cycle report data.
        :returns: Path to the written file.
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        date = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"{date}-cycle-{report.cycle:03d}.md"
        path = self._dir / filename

        lines = [
            f"# Cycle Report {report.cycle}",
            "",
            f"**Timestamp:** {report.timestamp}",
            "",
            "## Specs Processed",
        ]
        for spec_id in report.specs_processed:
            lines.append(f"- {spec_id}")
        if not report.specs_processed:
            lines.append("- (none)")

        lines.append("")
        lines.append("## Agents Spawned")
        for agent in report.agents_spawned:
            lines.append(f"- {agent}")
        if not report.agents_spawned:
            lines.append("- (none)")

        if report.errors:
            lines.append("")
            lines.append("## Errors")
            for error in report.errors:
                lines.append(f"- {error}")

        content = "\n".join(lines) + "\n"
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))
        return str(path)

    def write_escalation(self, spec_id: str, reason: str, details: str = "") -> str:
        """Write an escalation file for EA to pick up.

        :param spec_id: The spec that triggered the escalation.
        :param reason: Short reason for escalation.
        :param details: Additional details.
        :returns: Path to the written file.
        """
        esc_dir = self._dir / "escalations"
        esc_dir.mkdir(parents=True, exist_ok=True)
        date = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"{date}-{spec_id}.md"
        path = esc_dir / filename

        content = (
            f"# Escalation: {spec_id}\n\n"
            f"**Date:** {date}\n"
            f"**Reason:** {reason}\n\n"
            f"## Details\n\n{details or 'No additional details.'}\n"
        )
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))
        return str(path)
