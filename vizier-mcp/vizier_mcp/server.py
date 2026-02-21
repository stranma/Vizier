"""FastMCP server entry point for the Vizier MCP server.

Registers all 12 tools and provides the create_server factory
for both production use and testing.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from vizier_mcp.config import ServerConfig
from vizier_mcp.tools.config_tool import project_get_config as _project_get_config
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

__version__ = "0.7.0"
TOOL_COUNT = 12


def create_server(config: ServerConfig | None = None) -> FastMCP:
    """Create and configure the Vizier MCP server.

    Registers all 12 tools with config injected via closures.

    :param config: Server configuration. Uses defaults if None.
    :return: Configured FastMCP instance ready to run.
    """
    if config is None:
        config = ServerConfig()

    mcp = FastMCP(
        name="vizier-mcp",
        version=__version__,
        instructions="Vizier MCP server providing spec lifecycle, sentinel security, and orchestration tools.",
    )

    cfg = config

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
        return _spec_create(cfg, project_id, title, description, complexity, artifacts, criteria, depends_on)

    @mcp.tool()
    def spec_read(project_id: str, spec_id: str) -> dict[str, Any]:
        """Read spec contents and metadata."""
        return _spec_read(cfg, project_id, spec_id)

    @mcp.tool()
    def spec_list(project_id: str, status_filter: str | None = None) -> dict[str, Any]:
        """List specs with optional status filter."""
        return _spec_list(cfg, project_id, status_filter)

    @mcp.tool()
    def spec_transition(
        project_id: str,
        spec_id: str,
        new_status: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Validate and execute a spec state transition."""
        return _spec_transition(cfg, project_id, spec_id, new_status, agent_role)

    @mcp.tool()
    def spec_update(
        project_id: str,
        spec_id: str,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Update mutable spec fields (retry_count, assigned_agent, etc.)."""
        return _spec_update(cfg, project_id, spec_id, fields)

    @mcp.tool()
    def spec_write_feedback(
        project_id: str,
        spec_id: str,
        verdict: str,
        feedback: str,
        reviewer: str = "quality_gate",
    ) -> dict[str, Any]:
        """Write QG feedback or rejection reason."""
        return _spec_write_feedback(cfg, project_id, spec_id, verdict, feedback, reviewer)

    @mcp.tool()
    def sentinel_check_write(
        project_id: str,
        file_path: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Validate a file write against Sentinel policy."""
        return _sentinel_check_write(cfg, project_id, file_path, agent_role)

    @mcp.tool()
    async def run_command_checked(
        project_id: str,
        command: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Execute a shell command after Sentinel validation."""
        return await _run_command_checked(cfg, project_id, command, agent_role)

    @mcp.tool()
    async def web_fetch_checked(
        url: str,
        agent_role: str,
    ) -> dict[str, Any]:
        """Fetch a URL and scan content for prompt injection."""
        return await _web_fetch_checked(url, agent_role)

    @mcp.tool()
    def orch_write_ping(
        project_id: str,
        spec_id: str,
        urgency: str,
        message: str,
    ) -> dict[str, Any]:
        """Write a supervisor notification (QUESTION, BLOCKER, or IMPOSSIBLE)."""
        return _orch_write_ping(cfg, project_id, spec_id, urgency, message)

    @mcp.tool()
    def project_get_config(project_id: str) -> dict[str, Any]:
        """Get project configuration (write-set, criteria, settings)."""
        return _project_get_config(cfg, project_id)

    @mcp.tool()
    def secret_check(name: str) -> dict[str, Any]:
        """Check whether a named secret is available (without revealing its value)."""
        return _secret_check(name)

    return mcp


if __name__ == "__main__":
    server = create_server()
    server.run()
