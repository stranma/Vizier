"""Scout research report: build, write, and read research.md."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from vizier.core.scout.sources import SearchResult  # noqa: TC001


@dataclass
class ResearchReport:
    """Structured research report produced by the Scout agent."""

    spec_id: str
    decision: str
    summary: str = ""
    recommendation: str = "BUILD_FROM_SCRATCH"
    solutions: list[SearchResult] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)


def build_report(report: ResearchReport) -> str:
    """Render a ResearchReport as markdown.

    :param report: The research report to render.
    :returns: Markdown string.
    """
    lines = [
        f"# Prior Art Research: {report.spec_id}",
        "",
        "## Summary",
        report.summary or "No research performed.",
        "",
        "## Recommendation",
        report.recommendation,
        "",
    ]

    if report.solutions:
        lines.append("## Existing Solutions")
        lines.append("")
        for sol in report.solutions:
            lines.append(f"### {sol.name}")
            lines.append(f"- **Source:** {sol.source}")
            lines.append(f"- **URL:** {sol.url}")
            if sol.license:
                lines.append(f"- **License:** {sol.license}")
            if sol.metric:
                lines.append(f"- **Stars/Downloads:** {sol.metric}")
            lines.append(f"- **Relevance:** {sol.relevance}")
            if sol.description:
                lines.append(f"- **Notes:** {sol.description}")
            lines.append("")

    if report.queries:
        lines.append("## Search Queries Used")
        for q in report.queries:
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines)


def write_report(spec_dir: str, report: ResearchReport) -> str:
    """Write a research report as research.md in the spec directory.

    :param spec_dir: Directory containing the spec file.
    :param report: The research report to write.
    :returns: Path to the written file.
    """
    content = build_report(report)
    path = Path(spec_dir) / "research.md"
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))

    return str(path)


def read_report(spec_dir: str) -> str | None:
    """Read research.md from a spec directory if it exists.

    :param spec_dir: Directory containing the spec file.
    :returns: File contents or None if not found.
    """
    path = Path(spec_dir) / "research.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None
