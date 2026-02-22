"""Observability MCP tools for querying structured logs (D82).

Provides system_get_logs and system_get_errors for agents and operators
to inspect server behavior without SSH access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vizier_mcp.logging_structured import StructuredLogger


def system_get_logs(
    slog: StructuredLogger,
    level: str | None = None,
    module: str | None = None,
    event: str | None = None,
    since_minutes: int = 60,
    limit: int = 100,
    spec_id: str | None = None,
) -> dict[str, Any]:
    """Query structured logs with filters.

    :param slog: The structured logger instance.
    :param level: Filter by log level (INFO, ERROR, WARN, DEBUG).
    :param module: Filter by source module.
    :param event: Filter by event type (tool_call, tool_error, spec_transition, etc.).
    :param since_minutes: Only return entries from the last N minutes.
    :param limit: Maximum number of entries to return.
    :param spec_id: Filter by spec_id in entry data.
    :return: {"entries": list, "total_matched": int, "truncated": bool}
    """
    return slog.read_entries(
        level=level,
        module=module,
        event=event,
        since_minutes=since_minutes,
        limit=limit,
        spec_id=spec_id,
    )


def system_get_errors(
    slog: StructuredLogger,
    since_minutes: int = 60,
    limit: int = 50,
) -> dict[str, Any]:
    """Get recent ERROR-level log entries.

    Convenience wrapper around system_get_logs for error triage.

    :param slog: The structured logger instance.
    :param since_minutes: Only return errors from the last N minutes.
    :param limit: Maximum number of errors to return.
    :return: {"errors": list, "total": int}
    """
    result = slog.read_entries(level="ERROR", since_minutes=since_minutes, limit=limit)
    return {
        "errors": result["entries"],
        "total": result["total_matched"],
    }
