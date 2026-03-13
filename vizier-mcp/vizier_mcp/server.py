"""FastMCP server entry point for Vizier v2.

Registers realm and container management tools.
All tool calls are instrumented with structured JSONL logging.
"""

from __future__ import annotations

import functools
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from fastmcp import FastMCP

from vizier_mcp.config import ServerConfig
from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.realm import RealmManager
from vizier_mcp.tools.agent import agent_kill as _agent_kill
from vizier_mcp.tools.agent import knowledge_link as _knowledge_link
from vizier_mcp.tools.agent import pasha_launch as _pasha_launch
from vizier_mcp.tools.agent import pasha_status as _pasha_status
from vizier_mcp.tools.container import container_start as _container_start
from vizier_mcp.tools.container import container_status as _container_status
from vizier_mcp.tools.container import container_stop as _container_stop
from vizier_mcp.tools.realm import realm_create_project as _realm_create_project
from vizier_mcp.tools.realm import realm_get_project as _realm_get_project
from vizier_mcp.tools.realm import realm_list_projects as _realm_list_projects

__version__ = "1.0.0"
TOOL_COUNT = 10


def _logged_sync(slog: StructuredLogger, tool_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a sync tool with structured logging."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.monotonic()
        try:
            result = fn(*args, **kwargs)
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=True)
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=False, data={"error": str(exc)})
            raise

    return wrapper


def _logged_async(slog: StructuredLogger, tool_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an async tool with structured logging."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        t0 = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=True)
            return result
        except Exception as exc:
            duration = (time.monotonic() - t0) * 1000
            slog.log_tool_call(tool_name, duration, success=False, data={"error": str(exc)})
            raise

    return wrapper


def create_server(config: ServerConfig | None = None) -> FastMCP:
    """Create and configure the Vizier MCP server.

    Registers realm and container tools with config injected via closures.

    :param config: Server configuration. Uses defaults if None.
    :return: Configured FastMCP instance ready to run.
    """
    if config is None:
        config = ServerConfig()

    mcp = FastMCP(
        name="vizier-mcp",
        version=__version__,
        instructions="Vizier MCP server providing realm management and container lifecycle tools.",
    )

    cfg = config
    assert cfg.log_dir is not None
    slog = StructuredLogger(cfg.log_dir, cfg.log_max_size_mb * 1024 * 1024, cfg.log_max_files)
    realm = RealmManager(cfg.vizier_root)

    slog.log("INFO", "server", "system_startup", {"version": __version__, "tool_count": TOOL_COUNT})

    # -- Realm tools --

    @mcp.tool()
    def realm_list_projects(type_filter: str | None = None) -> dict[str, Any]:
        """List all projects and knowledge projects in the realm."""
        return _logged_sync(slog, "realm_list_projects", _realm_list_projects)(realm, type_filter)

    @mcp.tool()
    async def realm_create_project(
        project_id: str,
        project_type: str = "project",
        git_url: str | None = None,
        template: str = "stranma/claude-code-python-template",
    ) -> dict[str, Any]:
        """Initialize a new project or knowledge project in the realm."""
        return await _logged_async(slog, "realm_create_project", _realm_create_project)(
            realm, project_id, project_type, git_url, template
        )

    @mcp.tool()
    def realm_get_project(project_id: str) -> dict[str, Any]:
        """Get project config, status, and recent PRs."""
        return _logged_sync(slog, "realm_get_project", _realm_get_project)(realm, project_id)

    # -- Container tools --

    @mcp.tool()
    async def container_start(project_id: str) -> dict[str, Any]:
        """Build and start a project's devcontainer."""
        return await _logged_async(slog, "container_start", _container_start)(realm, project_id)

    @mcp.tool()
    async def container_stop(project_id: str) -> dict[str, Any]:
        """Stop a project's devcontainer."""
        return await _logged_async(slog, "container_stop", _container_stop)(realm, project_id)

    @mcp.tool()
    async def container_status(project_id: str) -> dict[str, Any]:
        """Check container state for a project."""
        return await _logged_async(slog, "container_status", _container_status)(realm, project_id)

    # -- Agent tools --

    @mcp.tool()
    async def pasha_launch(
        project_id: str,
        task: str,
        acceptance_criteria: list[str] | None = None,
        cost_limit: float | None = None,
    ) -> dict[str, Any]:
        """Launch a Pasha agent inside a project's devcontainer using its manifest."""
        return await _logged_async(slog, "pasha_launch", _pasha_launch)(
            realm, project_id, task, acceptance_criteria, cost_limit
        )

    @mcp.tool()
    async def pasha_status(project_id: str) -> dict[str, Any]:
        """Check the status of a Pasha agent in a project."""
        return await _logged_async(slog, "pasha_status", _pasha_status)(realm, project_id)

    @mcp.tool()
    async def agent_kill(project_id: str) -> dict[str, Any]:
        """Kill a running Pasha agent in a project's container."""
        return await _logged_async(slog, "agent_kill", _agent_kill)(realm, project_id)

    # -- Knowledge tools --

    @mcp.tool()
    async def knowledge_link(project_id: str, knowledge_project_id: str) -> dict[str, Any]:
        """Link a knowledge project to a work project for shared context."""
        return await _logged_async(slog, "knowledge_link", _knowledge_link)(realm, project_id, knowledge_project_id)

    return mcp


if __name__ == "__main__":
    server = create_server()
    server.run()
