"""System status MCP tool (D82, Phase 9).

Returns operational intelligence: server info, spec summary,
recent activity metrics, and unacknowledged alerts. Goes beyond
the health endpoint by providing actionable data for agents and operators.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.spec import SpecStatus
from vizier_mcp.tools._spec_utils import parse_spec_metadata

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig
    from vizier_mcp.logging_structured import StructuredLogger

_SERVER_START_TIME = time.monotonic()


def _read_unacknowledged_alerts(config: ServerConfig, project_id: str | None = None) -> list[dict[str, Any]]:
    """Read unacknowledged alerts from the alerts directory.

    :param config: Server configuration.
    :param project_id: Optional project filter. None = all projects.
    :return: List of alert dicts.
    """
    assert config.alerts_dir is not None
    if not config.alerts_dir.exists():
        return []

    alerts: list[dict[str, Any]] = []
    for alert_file in sorted(config.alerts_dir.glob("*.json")):
        try:
            data = json.loads(alert_file.read_text(encoding="utf-8"))
            if data.get("acknowledged", False):
                continue
            if project_id and data.get("project_id") != project_id:
                continue
            alerts.append(data)
        except Exception:
            continue
    return alerts


def system_get_status(
    config: ServerConfig,
    slog: StructuredLogger,
    version: str,
    tool_count: int,
    project_id: str | None = None,
) -> dict[str, Any]:
    """Return operational status of the Vizier MCP server.

    :param config: Server configuration.
    :param slog: Structured logger for recent activity.
    :param version: Server version string.
    :param tool_count: Number of registered tools.
    :param project_id: Optional project filter. None = system-wide.
    :return: Status dict with server, specs, activity, and alerts sections.
    """
    uptime_s = round(time.monotonic() - _SERVER_START_TIME, 1)

    server_info = {
        "version": version,
        "tool_count": tool_count,
        "uptime_seconds": uptime_s,
    }

    specs_by_status: dict[str, int] = {s.value: 0 for s in SpecStatus}
    stuck_specs: list[dict[str, Any]] = []
    in_progress_specs: list[dict[str, Any]] = []
    now = datetime.now(UTC)

    assert config.projects_dir is not None
    if project_id:
        project_dirs = [config.projects_dir / project_id]
    else:
        project_dirs = [d for d in config.projects_dir.iterdir() if d.is_dir()] if config.projects_dir.exists() else []

    for proj_dir in project_dirs:
        specs_dir = proj_dir / "specs"
        if not specs_dir.exists():
            continue
        for spec_dir in specs_dir.iterdir():
            if not spec_dir.is_dir():
                continue
            spec_file = spec_dir / "spec.md"
            if not spec_file.exists():
                continue
            meta = parse_spec_metadata(spec_file)
            if meta is None:
                continue

            status_val = meta.status.value
            specs_by_status[status_val] = specs_by_status.get(status_val, 0) + 1

            if meta.status == SpecStatus.STUCK:
                age_minutes = (now - meta.updated_at).total_seconds() / 60
                stuck_specs.append(
                    {
                        "spec_id": meta.spec_id,
                        "project_id": meta.project_id,
                        "title": meta.title,
                        "stuck_since": meta.updated_at.isoformat(),
                        "age_minutes": round(age_minutes, 1),
                        "retry_count": meta.retry_count,
                    }
                )

            if meta.status == SpecStatus.IN_PROGRESS:
                claimed = meta.claimed_at or meta.updated_at
                age_minutes = (now - claimed).total_seconds() / 60
                in_progress_specs.append(
                    {
                        "spec_id": meta.spec_id,
                        "project_id": meta.project_id,
                        "title": meta.title,
                        "claimed_at": claimed.isoformat(),
                        "age_minutes": round(age_minutes, 1),
                        "assigned_agent": meta.assigned_agent,
                    }
                )

    recent_activity = _get_recent_activity(slog)
    alerts = _read_unacknowledged_alerts(config, project_id)

    return {
        "server": server_info,
        "specs": {
            "by_status": specs_by_status,
            "stuck": stuck_specs,
            "in_progress": in_progress_specs,
        },
        "recent_activity": recent_activity,
        "alerts": alerts,
    }


def _get_recent_activity(slog: StructuredLogger) -> dict[str, Any]:
    """Get recent activity summary from structured logs."""
    transitions = slog.read_entries(event="spec_transition", since_minutes=60, limit=1000)
    errors = slog.read_entries(level="ERROR", since_minutes=60, limit=1000)
    sentinel_denials = slog.read_entries(event="sentinel_decision", since_minutes=60, limit=1000)

    return {
        "transitions_1h": transitions["total_matched"],
        "errors_1h": errors["total_matched"],
        "sentinel_denials_1h": sentinel_denials["total_matched"],
    }
