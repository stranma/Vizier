"""Audit query tools for the Imperial Spymaster observability layer (D84).

Provides audit_query, audit_timeline, and audit_stats tools for
querying the automatic MCP tool call audit log.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vizier_mcp.audit_logger import AuditLogger


def audit_query(
    alog: AuditLogger,
    project_id: str | None = None,
    spec_id: str | None = None,
    tool_name: str | None = None,
    agent_role: str | None = None,
    since_minutes: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Query the audit log with filters.

    :param alog: AuditLogger instance.
    :param project_id: Filter by project.
    :param spec_id: Filter by spec.
    :param tool_name: Filter by tool name.
    :param agent_role: Filter by agent role.
    :param since_minutes: Only entries from the last N minutes.
    :param limit: Maximum entries to return.
    :return: {"entries": list, "total": int}
    """
    entries = alog.read_entries(
        project_id=project_id,
        spec_id=spec_id,
        tool_name=tool_name,
        agent_role=agent_role,
        since_minutes=since_minutes,
        limit=limit,
    )
    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "total": len(entries),
    }


def audit_timeline(
    alog: AuditLogger,
    project_id: str,
    spec_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    """Get a chronological timeline of all tool calls for a spec.

    :param alog: AuditLogger instance.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param limit: Maximum entries to return.
    :return: Chronological timeline with summary stats.
    """
    entries = alog.read_entries(
        project_id=project_id,
        spec_id=spec_id,
        limit=limit,
    )
    entries.sort(key=lambda e: e.recorded_at)

    timeline = []
    for e in entries:
        timeline.append(
            {
                "timestamp": e.recorded_at.isoformat(),
                "tool": e.tool_name,
                "agent_role": e.agent_role,
                "success": e.success,
                "duration_ms": e.duration_ms,
                "summary": _summarize_call(e.tool_name, e.kwargs, e.result),
            }
        )

    agents_seen = sorted({e.agent_role for e in entries if e.agent_role})
    total_duration = sum(e.duration_ms for e in entries)

    return {
        "project_id": project_id,
        "spec_id": spec_id,
        "timeline": timeline,
        "total_calls": len(entries),
        "agents": agents_seen,
        "total_duration_ms": round(total_duration, 2),
    }


def audit_stats(
    alog: AuditLogger,
    project_id: str | None = None,
    since_minutes: int | None = None,
) -> dict[str, Any]:
    """Get aggregate statistics from the audit log.

    :param alog: AuditLogger instance.
    :param project_id: Filter by project.
    :param since_minutes: Only entries from the last N minutes.
    :return: Stats including call counts, error rates, timing.
    """
    entries = alog.read_entries(
        project_id=project_id,
        since_minutes=since_minutes,
        limit=10000,
    )

    tool_counts: Counter[str] = Counter()
    agent_counts: Counter[str] = Counter()
    error_count = 0
    total_duration = 0.0

    for e in entries:
        tool_counts[e.tool_name] += 1
        if e.agent_role:
            agent_counts[e.agent_role] += 1
        if not e.success:
            error_count += 1
        total_duration += e.duration_ms

    total = len(entries)
    return {
        "total_calls": total,
        "error_count": error_count,
        "error_rate": round(error_count / total, 4) if total > 0 else 0.0,
        "total_duration_ms": round(total_duration, 2),
        "avg_duration_ms": round(total_duration / total, 2) if total > 0 else 0.0,
        "by_tool": dict(tool_counts.most_common()),
        "by_agent": dict(agent_counts.most_common()),
    }


def _summarize_call(tool_name: str, kwargs: dict[str, Any], result: dict[str, Any]) -> str:
    """Generate a one-line summary of a tool call for timeline display."""
    if tool_name == "spec_create":
        return f"Created spec: {kwargs.get('title', '?')}"
    if tool_name == "spec_transition":
        return f"Transitioned to {kwargs.get('new_status', '?')}"
    if tool_name in ("spec_read", "spec_list"):
        return f"{tool_name}({kwargs.get('project_id', '')})"
    if tool_name == "sentinel_check_write":
        allowed = result.get("allowed", "?")
        return f"Write check: {kwargs.get('file_path', '?')} -> {'allowed' if allowed else 'denied'}"
    if tool_name == "run_command_checked":
        cmd = kwargs.get("command", "?")
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        return f"Command: {cmd}"
    if tool_name == "budget_record":
        return f"Budget: {kwargs.get('event_type', '?')} ${kwargs.get('cost_estimate', 0)}"
    if tool_name == "trace_record":
        return f"Trace: [{kwargs.get('action_type', '?')}] {kwargs.get('summary', '')[:60]}"
    return f"{tool_name}()"
