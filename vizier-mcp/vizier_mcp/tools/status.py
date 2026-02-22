"""System status MCP tool (D82, Phase 9).

Returns operational intelligence: server info, spec summary,
and recent activity metrics. Goes beyond the health endpoint
by providing actionable data for agents and operators.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import yaml

from vizier_mcp.models.spec import SpecMetadata, SpecStatus

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig
    from vizier_mcp.logging_structured import StructuredLogger

_SERVER_START_TIME = time.monotonic()


def _parse_spec_metadata(spec_file: Path) -> SpecMetadata | None:
    """Parse spec.md frontmatter into SpecMetadata, returning None on error."""
    try:
        content = spec_file.read_text()
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return None
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx == -1:
            return None
        frontmatter = "\n".join(lines[1:end_idx])
        meta_dict = yaml.safe_load(frontmatter) or {}
        return SpecMetadata(**meta_dict)
    except Exception:
        return None


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
    :return: Status dict with server, specs, and activity sections.
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
            meta = _parse_spec_metadata(spec_file)
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

    return {
        "server": server_info,
        "specs": {
            "by_status": specs_by_status,
            "stuck": stuck_specs,
            "in_progress": in_progress_specs,
        },
        "recent_activity": recent_activity,
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
