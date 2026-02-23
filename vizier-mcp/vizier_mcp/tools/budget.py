"""Budget tracking tools for cost visibility.

Provides budget_record and budget_summary tools for recording
and querying project-level cost events. Storage is append-only
JSONL at {projects_dir}/{project_id}/.vizier/budget/events.jsonl.

After each budget_record, checks project totals against configured
soft/hard limits and writes alert files when thresholds are exceeded.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.alerts import AlertData, AlertSeverity, AlertType
from vizier_mcp.models.budget import BudgetEvent

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig


def _budget_dir(config: ServerConfig, project_id: str) -> Path:
    """Return the budget directory for a project."""
    assert config.projects_dir is not None
    return config.projects_dir / project_id / ".vizier" / "budget"


def _budget_file(config: ServerConfig, project_id: str) -> Path:
    """Return the JSONL budget events file for a project."""
    return _budget_dir(config, project_id) / "events.jsonl"


def _append_event(config: ServerConfig, event: BudgetEvent) -> Path:
    """Append a budget event to the JSONL file, creating dirs as needed."""
    bdir = _budget_dir(config, event.project_id)
    bdir.mkdir(parents=True, exist_ok=True)
    bfile = bdir / "events.jsonl"
    line = event.model_dump_json() + "\n"
    with open(bfile, "a", encoding="utf-8") as f:
        f.write(line)
    return bfile


def _read_events(config: ServerConfig, project_id: str) -> list[BudgetEvent]:
    """Read all budget events from the JSONL file."""
    bfile = _budget_file(config, project_id)
    if not bfile.exists():
        return []
    events: list[BudgetEvent] = []
    for line in bfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(BudgetEvent.model_validate_json(line))
        except Exception:
            continue
    return events


def _has_unacknowledged_alert(config: ServerConfig, alert_type: str, project_id: str) -> bool:
    """Check if an unacknowledged alert of the given type+project already exists."""
    assert config.alerts_dir is not None
    if not config.alerts_dir.exists():
        return False
    for alert_file in config.alerts_dir.glob("*.json"):
        try:
            data = json.loads(alert_file.read_text(encoding="utf-8"))
            if (
                data.get("alert_type") == alert_type
                and data.get("project_id") == project_id
                and not data.get("acknowledged", False)
            ):
                return True
        except Exception:
            continue
    return False


def _write_alert(config: ServerConfig, alert: AlertData) -> Path:
    """Write an alert JSON file to the alerts directory."""
    assert config.alerts_dir is not None
    config.alerts_dir.mkdir(parents=True, exist_ok=True)
    ts = alert.created_at.strftime("%Y%m%dT%H%M%S%f")
    filename = f"{ts}-{alert.alert_type}-{alert.project_id}.json"
    alert_path = config.alerts_dir / filename
    alert_path.write_text(alert.model_dump_json(indent=2), encoding="utf-8")
    return alert_path


def _check_budget_thresholds(config: ServerConfig, project_id: str) -> list[str]:
    """Check project budget against soft/hard limits and write alerts if exceeded.

    :return: List of alert types triggered (for testing visibility).
    """
    events = _read_events(config, project_id)
    total_cost = sum(e.cost_estimate for e in events)
    triggered: list[str] = []

    if total_cost >= config.budget.hard_limit_usd:
        alert_type = AlertType.budget_hard_limit
        if not _has_unacknowledged_alert(config, alert_type, project_id):
            alert = AlertData(
                alert_type=alert_type,
                project_id=project_id,
                message=f"Project '{project_id}' has exceeded the hard budget limit of ${config.budget.hard_limit_usd:.2f} (current: ${total_cost:.2f})",
                severity=AlertSeverity.critical,
                data={"total_cost": round(total_cost, 6), "hard_limit": config.budget.hard_limit_usd},
            )
            _write_alert(config, alert)
            triggered.append(alert_type)
    elif total_cost >= config.budget.soft_limit_usd:
        alert_type = AlertType.budget_soft_limit
        if not _has_unacknowledged_alert(config, alert_type, project_id):
            alert = AlertData(
                alert_type=alert_type,
                project_id=project_id,
                message=f"Project '{project_id}' has exceeded the soft budget limit of ${config.budget.soft_limit_usd:.2f} (current: ${total_cost:.2f})",
                severity=AlertSeverity.warning,
                data={"total_cost": round(total_cost, 6), "soft_limit": config.budget.soft_limit_usd},
            )
            _write_alert(config, alert)
            triggered.append(alert_type)

    return triggered


def budget_record(
    config: ServerConfig,
    project_id: str,
    event_type: str,
    cost_estimate: float,
    spec_id: str | None = None,
    agent_role: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a budget event for cost tracking.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param event_type: Type of cost event (e.g. haiku_eval, spec_attempt, web_fetch, custom).
    :param cost_estimate: Estimated cost in USD (must be >= 0).
    :param spec_id: Optional spec identifier this cost is associated with.
    :param agent_role: Role of the agent incurring the cost.
    :param metadata: Optional additional metadata.
    :return: {"recorded": True, "event": dict} on success, {"error": str} on failure.
    """
    if cost_estimate < 0:
        return {"error": "cost_estimate must be >= 0"}

    assert config.projects_dir is not None

    try:
        event = BudgetEvent(
            project_id=project_id,
            spec_id=spec_id,
            event_type=event_type,
            cost_estimate=cost_estimate,
            agent_role=agent_role,
            metadata=metadata or {},
        )
        _append_event(config, event)
        alerts_triggered = _check_budget_thresholds(config, project_id)
        result: dict[str, Any] = {"recorded": True, "event": event.model_dump(mode="json")}
        if alerts_triggered:
            result["alerts_triggered"] = alerts_triggered
        return result
    except Exception as exc:
        return {"error": str(exc)}


def budget_summary(
    config: ServerConfig,
    project_id: str,
    since_minutes: int | None = None,
    spec_id: str | None = None,
    event_type: str | None = None,
    include_events: bool = False,
) -> dict[str, Any]:
    """Get aggregated cost summary for a project.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param since_minutes: Only include events from the last N minutes.
    :param spec_id: Filter by spec identifier.
    :param event_type: Filter by event type.
    :param include_events: Include individual events in response.
    :return: Summary dict with total_cost, event_count, by_event_type, by_spec.
    """
    assert config.projects_dir is not None

    try:
        events = _read_events(config, project_id)
    except Exception as exc:
        return {"error": str(exc)}

    if since_minutes is not None:
        cutoff = datetime.now(UTC) - timedelta(minutes=since_minutes)
        events = [e for e in events if e.recorded_at >= cutoff]

    if spec_id is not None:
        events = [e for e in events if e.spec_id == spec_id]

    if event_type is not None:
        events = [e for e in events if e.event_type == event_type]

    total_cost = round(sum(e.cost_estimate for e in events), 6)
    by_event_type: dict[str, float] = {}
    by_spec: dict[str, float] = {}
    for e in events:
        by_event_type[e.event_type] = round(by_event_type.get(e.event_type, 0.0) + e.cost_estimate, 6)
        if e.spec_id:
            by_spec[e.spec_id] = round(by_spec.get(e.spec_id, 0.0) + e.cost_estimate, 6)

    result: dict[str, Any] = {
        "project_id": project_id,
        "total_cost": total_cost,
        "event_count": len(events),
        "by_event_type": by_event_type,
        "by_spec": by_spec,
    }

    if include_events:
        result["events"] = [e.model_dump(mode="json") for e in events]

    return result
