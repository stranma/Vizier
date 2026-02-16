"""Retrospective analysis: failure patterns, metrics, and cost tracking."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

from pydantic import BaseModel, Field

from vizier.core.file_protocol.spec_io import list_specs
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.models.logging import AgentLogEntry  # noqa: TC001
from vizier.core.models.spec import SpecStatus

logger = logging.getLogger(__name__)


class FailurePattern(BaseModel):
    """A detected failure pattern from rejection/stuck history.

    :param pattern_type: Category of failure (repeated_rejection, stuck, high_retry).
    :param spec_ids: Spec IDs exhibiting this pattern.
    :param description: Human-readable description.
    :param frequency: How many times this pattern occurred.
    :param suggested_action: Recommended action.
    """

    pattern_type: str
    spec_ids: list[str] = Field(default_factory=list)
    description: str = ""
    frequency: int = 1
    suggested_action: str = ""


class SpecMetrics(BaseModel):
    """Aggregate metrics across specs for a project.

    :param total_specs: Total number of specs.
    :param done_count: Specs completed (DONE).
    :param stuck_count: Specs stuck (STUCK).
    :param rejected_count: Current REJECTED specs.
    :param avg_retries: Average retry count across completed specs.
    :param total_cost_usd: Total cost from agent logs.
    :param cost_per_spec: Average cost per completed spec.
    :param total_agent_calls: Total number of agent invocations.
    :param avg_duration_ms: Average agent invocation duration.
    """

    total_specs: int = 0
    done_count: int = 0
    stuck_count: int = 0
    rejected_count: int = 0
    avg_retries: float = 0.0
    total_cost_usd: float = 0.0
    cost_per_spec: float = 0.0
    total_agent_calls: int = 0
    avg_duration_ms: float = 0.0


class RetrospectiveAnalysis:
    """Analyzes project history for failure patterns and metrics.

    :param project_root: Root directory of the project.
    :param agent_log_path: Path to the agent-log.jsonl file.
    """

    def __init__(self, project_root: str | Path, agent_log_path: str | Path = "") -> None:
        self._root = Path(project_root)
        self._log_path = Path(agent_log_path) if agent_log_path else None

    def analyze_failure_patterns(self) -> list[FailurePattern]:
        """Scan specs for recurring failure patterns.

        :returns: List of detected failure patterns.
        """
        patterns: list[FailurePattern] = []
        all_specs = list_specs(str(self._root))

        stuck_specs = [s for s in all_specs if s.frontmatter.status == SpecStatus.STUCK]
        if stuck_specs:
            patterns.append(
                FailurePattern(
                    pattern_type="stuck",
                    spec_ids=[s.frontmatter.id for s in stuck_specs],
                    description=f"{len(stuck_specs)} spec(s) reached STUCK status after exhausting retries",
                    frequency=len(stuck_specs),
                    suggested_action="Review stuck specs for scope issues or missing prerequisites",
                )
            )

        high_retry_specs = [s for s in all_specs if s.frontmatter.retries >= 3]
        if high_retry_specs:
            patterns.append(
                FailurePattern(
                    pattern_type="high_retry",
                    spec_ids=[s.frontmatter.id for s in high_retry_specs],
                    description=f"{len(high_retry_specs)} spec(s) have 3+ retries, indicating difficulty",
                    frequency=len(high_retry_specs),
                    suggested_action="Consider re-decomposing these specs into smaller tasks",
                )
            )

        rejected_specs = [s for s in all_specs if s.frontmatter.status == SpecStatus.REJECTED]
        if rejected_specs:
            patterns.append(
                FailurePattern(
                    pattern_type="repeated_rejection",
                    spec_ids=[s.frontmatter.id for s in rejected_specs],
                    description=f"{len(rejected_specs)} spec(s) currently in REJECTED status",
                    frequency=len(rejected_specs),
                    suggested_action="Check Quality Gate feedback for common rejection reasons",
                )
            )

        feedback_patterns = self._analyze_feedback_files()
        patterns.extend(feedback_patterns)

        return patterns

    def _analyze_feedback_files(self) -> list[FailurePattern]:
        """Analyze feedback files for common rejection themes.

        :returns: Failure patterns from feedback analysis.
        """
        specs_dir = self._root / ".vizier" / "specs"
        if not specs_dir.exists():
            return []

        feedback_reasons: Counter[str] = Counter()

        for feedback_dir in specs_dir.rglob("feedback"):
            if not feedback_dir.is_dir():
                continue
            for feedback_file in feedback_dir.glob("*.md"):
                try:
                    content = feedback_file.read_text(encoding="utf-8").lower()
                    if "test" in content and ("fail" in content or "missing" in content):
                        feedback_reasons["test_failures"] += 1
                    if "lint" in content or "format" in content:
                        feedback_reasons["code_quality"] += 1
                    if "type" in content and ("error" in content or "annotation" in content):
                        feedback_reasons["type_errors"] += 1
                    if "criteria" in content and "not met" in content:
                        feedback_reasons["criteria_not_met"] += 1
                except Exception:
                    pass

        patterns: list[FailurePattern] = []
        for reason, count in feedback_reasons.most_common():
            if count >= 2:
                patterns.append(
                    FailurePattern(
                        pattern_type=f"feedback_{reason}",
                        description=f"Feedback theme '{reason}' appeared {count} times across rejections",
                        frequency=count,
                        suggested_action=f"Add '{reason}' checks to Worker's pre-submission validation",
                    )
                )

        return patterns

    def compute_metrics(self) -> SpecMetrics:
        """Compute aggregate metrics across all specs and agent logs.

        :returns: Project-level metrics.
        """
        all_specs = list_specs(str(self._root))

        done = [s for s in all_specs if s.frontmatter.status == SpecStatus.DONE]
        stuck = [s for s in all_specs if s.frontmatter.status == SpecStatus.STUCK]
        rejected = [s for s in all_specs if s.frontmatter.status == SpecStatus.REJECTED]

        total_retries = sum(s.frontmatter.retries for s in all_specs)
        avg_retries = total_retries / len(all_specs) if all_specs else 0.0

        log_entries = self._read_agent_logs()
        total_cost = sum(e.cost_usd for e in log_entries)
        total_duration = sum(e.duration_ms for e in log_entries)
        avg_duration = total_duration / len(log_entries) if log_entries else 0.0
        cost_per_spec = total_cost / len(done) if done else 0.0

        return SpecMetrics(
            total_specs=len(all_specs),
            done_count=len(done),
            stuck_count=len(stuck),
            rejected_count=len(rejected),
            avg_retries=round(avg_retries, 2),
            total_cost_usd=round(total_cost, 4),
            cost_per_spec=round(cost_per_spec, 4),
            total_agent_calls=len(log_entries),
            avg_duration_ms=round(avg_duration, 1),
        )

    def _read_agent_logs(self) -> list[AgentLogEntry]:
        """Read agent log entries from disk.

        :returns: List of log entries.
        """
        if self._log_path and self._log_path.exists():
            agent_logger = AgentLogger(self._log_path)
            return agent_logger.read_entries()
        return []

    def generate_analysis_report(self) -> str:
        """Generate a markdown analysis report.

        :returns: Formatted report string.
        """
        patterns = self.analyze_failure_patterns()
        metrics = self.compute_metrics()

        lines = [
            "# Retrospective Analysis",
            "",
            "## Metrics",
            "",
            f"- Total specs: {metrics.total_specs}",
            f"- Completed (DONE): {metrics.done_count}",
            f"- Stuck: {metrics.stuck_count}",
            f"- Currently rejected: {metrics.rejected_count}",
            f"- Average retries: {metrics.avg_retries}",
            f"- Total cost: ${metrics.total_cost_usd:.4f}",
            f"- Cost per completed spec: ${metrics.cost_per_spec:.4f}",
            f"- Total agent calls: {metrics.total_agent_calls}",
            f"- Average call duration: {metrics.avg_duration_ms:.1f}ms",
            "",
        ]

        if patterns:
            lines.append("## Failure Patterns")
            lines.append("")
            for p in patterns:
                lines.append(f"### {p.pattern_type} (x{p.frequency})")
                lines.append(f"{p.description}")
                if p.spec_ids:
                    lines.append(f"Specs: {', '.join(p.spec_ids)}")
                lines.append(f"Suggested: {p.suggested_action}")
                lines.append("")
        else:
            lines.append("## Failure Patterns")
            lines.append("")
            lines.append("No failure patterns detected.")
            lines.append("")

        return "\n".join(lines)
