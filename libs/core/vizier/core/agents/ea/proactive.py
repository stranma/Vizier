"""EA proactive behaviors: scheduled and event-driven triggers.

Each behavior checks conditions against the filesystem state and
produces a task string for the EA AgentRuntime to process.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum


class TriggerType(Enum):
    """Types of proactive triggers."""

    MORNING_BRIEFING = "morning_briefing"
    DEADLINE_WARNING = "deadline_warning"
    ESCALATION_ALERT = "escalation_alert"
    COMPLETION_NOTICE = "completion_notice"
    FOLLOWUP_REMINDER = "followup_reminder"


@dataclass
class ProactiveTrigger:
    """A proactive behavior trigger with context for the EA.

    :param trigger_type: Type of proactive behavior.
    :param message: Task message for the EA AgentRuntime.
    :param priority: Priority level (1=highest).
    :param context: Additional context data.
    """

    trigger_type: TriggerType
    message: str
    priority: int = 3
    context: dict[str, str] | None = None


def check_morning_briefing(*, hour: int | None = None) -> ProactiveTrigger | None:
    """Check if it's time for the morning briefing.

    :param hour: Current hour (0-23). If None, uses current time.
    :returns: Trigger if briefing is due, None otherwise.
    """
    if hour is None:
        hour = datetime.now(UTC).hour
    if hour == 8:
        return ProactiveTrigger(
            trigger_type=TriggerType.MORNING_BRIEFING,
            message=(
                "Generate the morning briefing for Sultan. "
                "List all active specs across all projects, highlight approaching deadlines, "
                "summarize overnight progress, and flag any items needing attention. "
                "Use send_briefing to deliver via Telegram."
            ),
            priority=1,
        )
    return None


def check_escalation_alerts(reports_dir: str) -> list[ProactiveTrigger]:
    """Check for unprocessed escalation files in reports directory.

    :param reports_dir: Path to the reports directory.
    :returns: List of escalation triggers found.
    """
    triggers: list[ProactiveTrigger] = []
    if not os.path.isdir(reports_dir):
        return triggers

    for project_name in os.listdir(reports_dir):
        esc_dir = os.path.join(reports_dir, project_name, "escalations")
        if not os.path.isdir(esc_dir):
            continue
        for filename in os.listdir(esc_dir):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(esc_dir, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                severity = data.get("severity", "medium")
                reason = data.get("reason", "Unknown escalation")
                triggers.append(
                    ProactiveTrigger(
                        trigger_type=TriggerType.ESCALATION_ALERT,
                        message=(
                            f"ESCALATION from project '{project_name}': {reason}. "
                            f"Severity: {severity}. Review the escalation and determine "
                            f"if Sultan needs to be notified immediately."
                        ),
                        priority=1 if severity in ("high", "critical") else 2,
                        context={"project": project_name, "file": filename},
                    )
                )
            except (json.JSONDecodeError, OSError):
                continue

    return triggers


def check_completion_notices(project_root: str) -> list[ProactiveTrigger]:
    """Check for recently completed specs to notify Sultan about.

    :param project_root: Path to the project root.
    :returns: List of completion notice triggers.
    """
    triggers: list[ProactiveTrigger] = []
    specs_dir = os.path.join(project_root, ".vizier", "specs")
    if not os.path.isdir(specs_dir):
        return triggers

    for spec_id in os.listdir(specs_dir):
        state_path = os.path.join(specs_dir, spec_id, "state.json")
        if not os.path.isfile(state_path):
            continue
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            if state.get("status") == "DONE" and not state.get("notified"):
                triggers.append(
                    ProactiveTrigger(
                        trigger_type=TriggerType.COMPLETION_NOTICE,
                        message=(
                            f"Spec '{spec_id}' has been completed. "
                            f"Read the spec to summarize what was done and ask Sultan "
                            f"if anyone should be notified about the completion."
                        ),
                        priority=2,
                        context={"spec_id": spec_id},
                    )
                )
        except (json.JSONDecodeError, OSError):
            continue

    return triggers


def check_deadline_warnings(
    commitments_dir: str,
    *,
    warning_days: int = 2,
) -> list[ProactiveTrigger]:
    """Check for approaching commitment deadlines.

    :param commitments_dir: Path to ea/commitments/ directory.
    :param warning_days: Days before deadline to warn.
    :returns: List of deadline warning triggers.
    """
    triggers: list[ProactiveTrigger] = []
    if not os.path.isdir(commitments_dir):
        return triggers

    now = datetime.now(UTC)
    for filename in os.listdir(commitments_dir):
        if not filename.endswith((".yaml", ".yml", ".json")):
            continue
        filepath = os.path.join(commitments_dir, filename)
        try:
            with open(filepath, encoding="utf-8") as f:
                content = f.read()
            if "deadline:" in content:
                for line in content.split("\n"):
                    if "deadline:" in line:
                        date_str = line.split("deadline:", 1)[1].strip().strip("'\"")
                        try:
                            deadline = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
                            days_left = (deadline - now).days
                            if 0 <= days_left <= warning_days:
                                commitment_name = filename.rsplit(".", 1)[0]
                                triggers.append(
                                    ProactiveTrigger(
                                        trigger_type=TriggerType.DEADLINE_WARNING,
                                        message=(
                                            f"DEADLINE WARNING: Commitment '{commitment_name}' "
                                            f"is due in {days_left} day(s). Check project progress "
                                            f"and alert Sultan if the deadline is at risk."
                                        ),
                                        priority=1 if days_left == 0 else 2,
                                        context={"commitment": commitment_name, "days_left": str(days_left)},
                                    )
                                )
                        except (ValueError, TypeError):
                            continue
        except OSError:
            continue

    return triggers


def collect_triggers(
    *,
    reports_dir: str = "",
    project_root: str = "",
    commitments_dir: str = "",
    hour: int | None = None,
) -> list[ProactiveTrigger]:
    """Collect all pending proactive triggers, sorted by priority.

    :param reports_dir: Path to reports directory for escalation checks.
    :param project_root: Path to project root for completion checks.
    :param commitments_dir: Path to ea/commitments/ for deadline checks.
    :param hour: Current hour for briefing check.
    :returns: Sorted list of triggers (highest priority first).
    """
    triggers: list[ProactiveTrigger] = []

    briefing = check_morning_briefing(hour=hour)
    if briefing is not None:
        triggers.append(briefing)

    if reports_dir:
        triggers.extend(check_escalation_alerts(reports_dir))

    if project_root:
        triggers.extend(check_completion_notices(project_root))

    if commitments_dir:
        triggers.extend(check_deadline_warnings(commitments_dir))

    triggers.sort(key=lambda t: t.priority)
    return triggers
