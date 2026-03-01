"""FastMCP server entry point for the Vizier MCP server.

Registers all tools and provides the create_server factory
for both production use and testing. All tool calls are instrumented
with structured JSONL logging (D82).
"""

from __future__ import annotations

import functools
import inspect
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from fastmcp import FastMCP
from pydantic import BaseModel

from vizier_mcp.audit_logger import AuditLogger
from vizier_mcp.config import ServerConfig
from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.tools.analytics import spec_analytics as _spec_analytics
from vizier_mcp.tools.audit import audit_query as _audit_query
from vizier_mcp.tools.audit import audit_stats as _audit_stats
from vizier_mcp.tools.audit import audit_timeline as _audit_timeline
from vizier_mcp.tools.budget import budget_record as _budget_record
from vizier_mcp.tools.budget import budget_summary as _budget_summary
from vizier_mcp.tools.config_tool import project_get_config as _project_get_config
from vizier_mcp.tools.learnings import learnings_extract as _learnings_extract
from vizier_mcp.tools.learnings import learnings_inject as _learnings_inject
from vizier_mcp.tools.learnings import learnings_list as _learnings_list
from vizier_mcp.tools.observability import system_get_errors as _system_get_errors
from vizier_mcp.tools.observability import system_get_logs as _system_get_logs
from vizier_mcp.tools.orchestration import orch_write_ping as _orch_write_ping
from vizier_mcp.tools.sentinel import run_command_checked as _run_command_checked
from vizier_mcp.tools.sentinel import secret_check as _secret_check
from vizier_mcp.tools.sentinel import sentinel_check_write as _sentinel_check_write
from vizier_mcp.tools.sentinel import web_fetch_checked as _web_fetch_checked
from vizier_mcp.tools.spec import spec_create as _spec_create
from vizier_mcp.tools.spec import spec_list as _spec_list
from vizier_mcp.tools.spec import spec_read as _spec_read
from vizier_mcp.tools.spec import spec_transition as _spec_transition
from vizier_mcp.tools.spec import spec_update as _spec_update
from vizier_mcp.tools.spec import spec_write_feedback as _spec_write_feedback
from vizier_mcp.tools.status import system_get_status as _system_get_status
from vizier_mcp.tools.trace import trace_query as _trace_query
from vizier_mcp.tools.trace import trace_record as _trace_record
from vizier_mcp.tools.trace import trace_timeline as _trace_timeline

__version__ = "0.13.0"
TOOL_COUNT = 27


def _extract_audit_kwargs(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Extract a serializable kwargs dict from positional+keyword args using function signature."""
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {k: v for k, v in bound.arguments.items() if not isinstance(v, BaseModel)}
    except (TypeError, ValueError):
        return dict(kwargs)


def _audited_sync(
    slog: StructuredLogger, alog: AuditLogger, tool_name: str, fn: Callable[..., Any]
) -> Callable[..., Any]:
    """Wrap a sync tool with structured logging AND audit recording."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        audit_kwargs = _extract_audit_kwargs(fn, args, kwargs)
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=True)
            entry = alog.build_entry(
                tool_name, audit_kwargs, result if isinstance(result, dict) else {}, True, "", duration
            )
            alog.record(entry)
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=False, data={"error": str(exc)})
            entry = alog.build_entry(tool_name, audit_kwargs, {}, False, str(exc), duration)
            alog.record(entry)
            raise

    return wrapper


def _audited_async(
    slog: StructuredLogger, alog: AuditLogger, tool_name: str, fn: Callable[..., Any]
) -> Callable[..., Any]:
    """Wrap an async tool with structured logging AND audit recording."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        audit_kwargs = _extract_audit_kwargs(fn, args, kwargs)
        t0 = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=True)
            entry = alog.build_entry(
                tool_name, audit_kwargs, result if isinstance(result, dict) else {}, True, "", duration
            )
            alog.record(entry)
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=False, data={"error": str(exc)})
            entry = alog.build_entry(tool_name, audit_kwargs, {}, False, str(exc), duration)
            alog.record(entry)
            raise

    return wrapper


def create_server(config: ServerConfig | None = None) -> FastMCP:
    """Create and configure the Vizier MCP server.

    Registers all tools with config injected via closures.
    All tool calls are instrumented with structured JSONL logging.

    :param config: Server configuration. Uses defaults if None.
    :return: Configured FastMCP instance ready to run.
    """
    if config is None:
        config = ServerConfig()

    mcp = FastMCP(
        name="vizier-mcp",
        version=__version__,
        instructions="Vizier MCP server providing spec lifecycle, sentinel security, orchestration, and observability tools.",
    )

    cfg = config
    assert cfg.log_dir is not None
    assert cfg.audit_dir is not None
    assert cfg.projects_dir is not None
    slog = StructuredLogger(cfg.log_dir, cfg.log_max_size_mb * 1024 * 1024, cfg.log_max_files)
    alog = AuditLogger(
        cfg.audit_dir,
        cfg.projects_dir,
        cfg.log_max_size_mb * 1024 * 1024,
        cfg.log_max_files,
        cfg.audit_max_output_chars,
    )
    slog.log("INFO", "server", "system_startup", {"version": __version__, "tool_count": TOOL_COUNT})

    @mcp.tool()
    def spec_create(
        project_id: str,
        title: str,
        description: str,
        complexity: str = "MEDIUM",
        artifacts: list[str] | None = None,
        criteria: list[str] | None = None,
        depends_on: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new spec in DRAFT state."""
        return _audited_sync(slog, alog, "spec_create", _spec_create)(
            cfg, project_id, title, description, complexity, artifacts, criteria, depends_on
        )

    @mcp.tool()
    def spec_read(project_id: str, spec_id: str) -> dict[str, Any]:
        """Read spec contents and metadata."""
        return _audited_sync(slog, alog, "spec_read", _spec_read)(cfg, project_id, spec_id)

    @mcp.tool()
    def spec_list(project_id: str, status_filter: str | None = None) -> dict[str, Any]:
        """List specs with optional status filter."""
        return _audited_sync(slog, alog, "spec_list", _spec_list)(cfg, project_id, status_filter)

    @mcp.tool()
    def spec_transition(
        project_id: str,
        spec_id: str,
        new_status: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Validate and execute a spec state transition."""
        return _audited_sync(slog, alog, "spec_transition", _spec_transition)(
            cfg, project_id, spec_id, new_status, agent_role
        )

    @mcp.tool()
    def spec_update(
        project_id: str,
        spec_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Update mutable spec fields (retry_count, assigned_agent, etc.)."""
        return _audited_sync(slog, alog, "spec_update", _spec_update)(cfg, project_id, spec_id, fields)

    @mcp.tool()
    def spec_write_feedback(
        project_id: str,
        spec_id: str,
        verdict: str,
        feedback: str,
        reviewer: str = "quality_gate",
    ) -> dict[str, Any]:
        """Write QG feedback or rejection reason."""
        return _audited_sync(slog, alog, "spec_write_feedback", _spec_write_feedback)(
            cfg, project_id, spec_id, verdict, feedback, reviewer
        )

    @mcp.tool()
    def sentinel_check_write(
        project_id: str,
        file_path: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Validate a file write against Sentinel policy."""
        result = _audited_sync(slog, alog, "sentinel_check_write", _sentinel_check_write)(
            cfg, project_id, file_path, agent_role
        )
        denied = not result.get("allowed", True)
        slog.log(
            "INFO",
            "sentinel",
            "sentinel_decision",
            {
                "tool": "sentinel_check_write",
                "project_id": project_id,
                "denied": denied,
                "agent_role": agent_role,
            },
        )
        return result

    @mcp.tool()
    async def run_command_checked(
        project_id: str,
        command: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Execute a shell command after Sentinel validation."""
        result = await _audited_async(slog, alog, "run_command_checked", _run_command_checked)(
            cfg, project_id, command, agent_role
        )
        denied = not result.get("allowed", True)
        slog.log(
            "INFO",
            "sentinel",
            "sentinel_decision",
            {
                "tool": "run_command_checked",
                "project_id": project_id,
                "denied": denied,
                "agent_role": agent_role,
            },
        )
        return result

    @mcp.tool()
    async def web_fetch_checked(
        project_id: str,
        url: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Fetch a URL and scan content for prompt injection."""
        result = await _audited_async(slog, alog, "web_fetch_checked", _web_fetch_checked)(
            cfg, project_id, url, agent_role
        )
        denied = not result.get("safe", True)
        slog.log(
            "INFO",
            "sentinel",
            "sentinel_decision",
            {
                "tool": "web_fetch_checked",
                "project_id": project_id,
                "denied": denied,
                "agent_role": agent_role,
            },
        )
        return result

    @mcp.tool()
    def orch_write_ping(
        project_id: str,
        spec_id: str,
        urgency: str,
        message: str,
    ) -> dict[str, Any]:
        """Write a supervisor notification (QUESTION, BLOCKER, or IMPOSSIBLE)."""
        return _audited_sync(slog, alog, "orch_write_ping", _orch_write_ping)(
            cfg, project_id, spec_id, urgency, message
        )

    @mcp.tool()
    def project_get_config(project_id: str) -> dict[str, Any]:
        """Get project configuration (write-set, criteria, settings)."""
        return _audited_sync(slog, alog, "project_get_config", _project_get_config)(cfg, project_id)

    @mcp.tool()
    def secret_check(name: str) -> dict[str, Any]:
        """Check whether a named secret is available (without revealing its value)."""
        return _audited_sync(slog, alog, "secret_check", _secret_check)(name)

    @mcp.tool()
    def system_get_logs(
        level: str | None = None,
        module: str | None = None,
        event: str | None = None,
        since_minutes: int = 60,
        limit: int = 100,
        spec_id: str | None = None,
    ) -> dict[str, Any]:
        """Query structured logs with filters."""
        return _system_get_logs(slog, level, module, event, since_minutes, limit, spec_id)

    @mcp.tool()
    def system_get_errors(
        since_minutes: int = 60,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get recent ERROR-level log entries."""
        return _system_get_errors(slog, since_minutes, limit)

    @mcp.tool()
    def system_get_status(
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Get operational status: server info, spec summary, recent activity."""
        return _system_get_status(cfg, slog, __version__, TOOL_COUNT, project_id)

    @mcp.tool()
    def spec_analytics(
        project_id: str,
    ) -> dict[str, Any]:
        """Get per-project spec analytics: throughput, timing, quality, sentinel."""
        return _spec_analytics(cfg, slog, project_id)

    @mcp.tool()
    def budget_record(
        project_id: str,
        event_type: str,
        cost_estimate: float,
        spec_id: str | None = None,
        agent_role: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a cost event for budget tracking."""
        return _audited_sync(slog, alog, "budget_record", _budget_record)(
            cfg, project_id, event_type, cost_estimate, spec_id, agent_role, metadata
        )

    @mcp.tool()
    def learnings_extract(
        project_id: str,
        spec_id: str | None = None,
    ) -> dict[str, Any]:
        """Extract failure learnings from REJECTED and STUCK specs."""
        return _audited_sync(slog, alog, "learnings_extract", _learnings_extract)(cfg, project_id, spec_id)

    @mcp.tool()
    def learnings_list(
        project_id: str,
        spec_id: str | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List failure learnings with optional filters."""
        return _audited_sync(slog, alog, "learnings_list", _learnings_list)(cfg, project_id, spec_id, category, limit)

    @mcp.tool()
    def learnings_inject(
        project_id: str,
        spec_id: str,
    ) -> dict[str, Any]:
        """Match and format failure learnings for injection into a Worker's context."""
        return _audited_sync(slog, alog, "learnings_inject", _learnings_inject)(cfg, project_id, spec_id)

    @mcp.tool()
    def budget_summary(
        project_id: str,
        since_minutes: int | None = None,
        spec_id: str | None = None,
        event_type: str | None = None,
        include_events: bool = False,
    ) -> dict[str, Any]:
        """Get aggregated cost summary for a project."""
        return _audited_sync(slog, alog, "budget_summary", _budget_summary)(
            cfg, project_id, since_minutes, spec_id, event_type, include_events
        )

    @mcp.tool()
    def audit_query(
        project_id: str | None = None,
        spec_id: str | None = None,
        tool_name: str | None = None,
        agent_role: str | None = None,
        since_minutes: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query the automatic audit log of all MCP tool calls."""
        return _audit_query(alog, project_id, spec_id, tool_name, agent_role, since_minutes, limit)

    @mcp.tool()
    def audit_timeline(
        project_id: str,
        spec_id: str,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Get chronological timeline of all tool calls for a spec."""
        return _audit_timeline(alog, project_id, spec_id, limit)

    @mcp.tool()
    def audit_stats(
        project_id: str | None = None,
        since_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Get aggregate statistics from the audit log."""
        return _audit_stats(alog, project_id, since_minutes)

    @mcp.tool()
    def trace_record(
        project_id: str,
        spec_id: str,
        agent_role: str,
        action_type: str,
        summary: str,
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a Golden Trace entry (agent reasoning, decisions, observations)."""
        return _audited_sync(slog, alog, "trace_record", _trace_record)(
            cfg, project_id, spec_id, agent_role, action_type, summary, detail, metadata
        )

    @mcp.tool()
    def trace_query(
        project_id: str,
        spec_id: str,
        action_type: str | None = None,
        agent_role: str | None = None,
        since_minutes: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query Golden Trace entries for a spec with filters."""
        return _trace_query(cfg, project_id, spec_id, action_type, agent_role, since_minutes, limit)

    @mcp.tool()
    def trace_timeline(
        project_id: str,
        spec_id: str,
    ) -> dict[str, Any]:
        """Get full chronological Golden Trace timeline for a spec."""
        return _trace_timeline(cfg, project_id, spec_id)

    return mcp


if __name__ == "__main__":
    server = create_server()
    server.run()
