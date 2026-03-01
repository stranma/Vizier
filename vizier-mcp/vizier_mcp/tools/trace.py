"""Golden Trace tools for agent-reported observability (D84).

Provides trace_record, trace_query, and trace_timeline tools
for agents to log reasoning, decisions, and observations
per-spec in append-only JSONL format.

Storage: {projects_dir}/{project_id}/specs/{spec_id}/.vizier/trace.jsonl
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.trace import TraceEntry

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig


def _trace_file(config: ServerConfig, project_id: str, spec_id: str) -> Path:
    """Return the per-spec trace JSONL file path."""
    assert config.projects_dir is not None
    return config.projects_dir / project_id / "specs" / spec_id / ".vizier" / "trace.jsonl"


def _append_trace(config: ServerConfig, entry: TraceEntry) -> Path:
    """Append a trace entry to the per-spec JSONL file."""
    tfile = _trace_file(config, entry.project_id, entry.spec_id)
    tfile.parent.mkdir(parents=True, exist_ok=True)
    line = entry.model_dump_json() + "\n"
    with open(tfile, "a", encoding="utf-8") as f:
        f.write(line)
    return tfile


def _read_traces(config: ServerConfig, project_id: str, spec_id: str) -> list[TraceEntry]:
    """Read all trace entries from the per-spec JSONL file."""
    tfile = _trace_file(config, project_id, spec_id)
    if not tfile.exists():
        return []
    entries: list[TraceEntry] = []
    for line in tfile.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(TraceEntry.model_validate_json(line))
        except Exception:
            continue
    return entries


def trace_record(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    agent_role: str,
    action_type: str,
    summary: str,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a Golden Trace entry for a spec.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param agent_role: Role of the agent recording the trace.
    :param action_type: Type of action (see TraceActionType enum for standard values).
    :param summary: Brief one-line summary of what happened.
    :param detail: Optional detailed description or reasoning.
    :param metadata: Optional additional metadata.
    :return: {"recorded": True, "entry": dict} on success, {"error": str} on failure.
    """
    if not project_id or not spec_id or not agent_role:
        return {"error": "project_id, spec_id, and agent_role are required"}
    if not action_type or not summary:
        return {"error": "action_type and summary are required"}

    try:
        entry = TraceEntry(
            project_id=project_id,
            spec_id=spec_id,
            agent_role=agent_role,
            action_type=action_type,
            summary=summary,
            detail=detail,
            metadata=metadata or {},
        )
        _append_trace(config, entry)
        return {"recorded": True, "entry": entry.model_dump(mode="json")}
    except Exception as exc:
        return {"error": str(exc)}


def trace_query(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    action_type: str | None = None,
    agent_role: str | None = None,
    since_minutes: int | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Query Golden Trace entries for a spec with optional filters.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param action_type: Filter by action type.
    :param agent_role: Filter by agent role.
    :param since_minutes: Only entries from the last N minutes.
    :param limit: Maximum entries to return.
    :return: {"entries": list, "total": int}
    """
    entries = _read_traces(config, project_id, spec_id)

    if since_minutes is not None:
        cutoff = datetime.now(UTC) - timedelta(minutes=since_minutes)
        entries = [e for e in entries if e.recorded_at >= cutoff]
    if action_type:
        entries = [e for e in entries if e.action_type == action_type]
    if agent_role:
        entries = [e for e in entries if e.agent_role == agent_role]

    entries.sort(key=lambda e: e.recorded_at, reverse=True)
    total = len(entries)
    entries = entries[:limit]

    return {
        "entries": [e.model_dump(mode="json") for e in entries],
        "total": total,
    }


def trace_timeline(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
) -> dict[str, Any]:
    """Get full chronological timeline of all trace entries for a spec.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :return: Chronological timeline with agent summary and duration.
    """
    entries = _read_traces(config, project_id, spec_id)
    entries.sort(key=lambda e: e.recorded_at)

    timeline = []
    for e in entries:
        timeline.append(
            {
                "timestamp": e.recorded_at.isoformat(),
                "agent_role": e.agent_role,
                "action_type": e.action_type,
                "summary": e.summary,
                "detail": e.detail,
                "metadata": e.metadata,
            }
        )

    agents_seen = sorted({e.agent_role for e in entries})
    action_types_seen = sorted({e.action_type for e in entries})

    duration_ms = 0.0
    if len(entries) >= 2:
        first = entries[0].recorded_at
        last = entries[-1].recorded_at
        duration_ms = (last - first).total_seconds() * 1000

    return {
        "project_id": project_id,
        "spec_id": spec_id,
        "timeline": timeline,
        "total_entries": len(entries),
        "agents": agents_seen,
        "action_types": action_types_seen,
        "duration_ms": round(duration_ms, 2),
    }
