"""Tests for FastMCP server integration (Vizier v2).

Tests that all tools are registered and callable via call_tool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from vizier_mcp.server import TOOL_COUNT, create_server

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from vizier_mcp.config import ServerConfig

EXPECTED_TOOLS = {
    "realm_list_projects",
    "realm_create_project",
    "realm_get_project",
    "container_start",
    "container_stop",
    "container_status",
    "pasha_launch",
    "pasha_status",
    "agent_kill",
    "knowledge_link",
}


@pytest.fixture
def server(config: ServerConfig) -> FastMCP:
    """Create a FastMCP server with test config."""
    return create_server(config)


def _data(result: object) -> dict:
    """Extract the structured dict from a FastMCP ToolResult."""
    return result.structured_content  # type: ignore[union-attr]


class TestServerToolRegistration:
    @pytest.mark.anyio
    async def test_tool_count(self, server: FastMCP) -> None:
        tools = await server.list_tools()
        assert len(tools) == TOOL_COUNT

    @pytest.mark.anyio
    async def test_all_tools_registered(self, server: FastMCP) -> None:
        tools = await server.list_tools()
        tool_names = {t.name for t in tools}
        assert tool_names == EXPECTED_TOOLS

    @pytest.mark.anyio
    async def test_tool_count_constant(self) -> None:
        assert TOOL_COUNT == 10


class TestRealmToolCallability:
    @pytest.mark.anyio
    async def test_realm_list_projects(self, server: FastMCP) -> None:
        result = await server.call_tool("realm_list_projects", {})
        data = _data(result)
        assert "projects" in data
        assert data["count"] == 0

    @pytest.mark.anyio
    async def test_realm_create_project(self, server: FastMCP) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=True)):
            result = await server.call_tool(
                "realm_create_project",
                {"project_id": "test-proj"},
            )
        data = _data(result)
        assert data["project_id"] == "test-proj"
        assert "error" not in data

    @pytest.mark.anyio
    async def test_realm_get_project_not_found(self, server: FastMCP) -> None:
        result = await server.call_tool("realm_get_project", {"project_id": "ghost"})
        data = _data(result)
        assert "error" in data

    @pytest.mark.anyio
    async def test_realm_create_then_get(self, server: FastMCP) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=False)):
            await server.call_tool(
                "realm_create_project",
                {"project_id": "roundtrip"},
            )
        result = await server.call_tool("realm_get_project", {"project_id": "roundtrip"})
        data = _data(result)
        assert data["id"] == "roundtrip"
        assert data["type"] == "project"


class TestContainerToolCallability:
    @pytest.mark.anyio
    async def test_container_start_no_project(self, server: FastMCP) -> None:
        result = await server.call_tool("container_start", {"project_id": "ghost"})
        data = _data(result)
        assert "error" in data

    @pytest.mark.anyio
    async def test_container_stop_no_project(self, server: FastMCP) -> None:
        result = await server.call_tool("container_stop", {"project_id": "ghost"})
        data = _data(result)
        assert "error" in data

    @pytest.mark.anyio
    async def test_container_status_no_project(self, server: FastMCP) -> None:
        result = await server.call_tool("container_status", {"project_id": "ghost"})
        data = _data(result)
        assert "error" in data
