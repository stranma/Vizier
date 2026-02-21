"""Tests for FastMCP server integration (Phase 4).

Tests that all 11 tools are registered and callable via call_tool,
plus end-to-end lifecycle tests through the MCP protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from vizier_mcp.server import TOOL_COUNT, create_server

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import FastMCP

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"

EXPECTED_TOOLS = {
    "spec_create",
    "spec_read",
    "spec_list",
    "spec_transition",
    "spec_update",
    "spec_write_feedback",
    "sentinel_check_write",
    "run_command_checked",
    "web_fetch_checked",
    "orch_write_ping",
    "project_get_config",
}


@pytest.fixture
def server(config: ServerConfig) -> FastMCP:
    """Create a FastMCP server with test config."""
    return create_server(config)


def _data(result: object) -> dict:
    """Extract the structured dict from a FastMCP ToolResult."""
    return result.structured_content  # type: ignore[union-attr]


class TestServerToolRegistration:
    """Tests for tool registration (AC-I1)."""

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
        assert TOOL_COUNT == 11


class TestToolCallability:
    """Tests that each tool is callable via call_tool (AC-I2, AC-I6, AC-I7)."""

    @pytest.mark.anyio
    async def test_spec_create(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Test Spec", "description": "A test spec"},
        )
        data = _data(result)
        assert "spec_id" in data

    @pytest.mark.anyio
    async def test_spec_read(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Read Test", "description": "test"},
        )
        spec_id = _data(create_result)["spec_id"]
        result = await server.call_tool(
            "spec_read",
            {"project_id": PROJECT_ID, "spec_id": spec_id},
        )
        data = _data(result)
        assert data["metadata"]["title"] == "Read Test"

    @pytest.mark.anyio
    async def test_spec_list(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("spec_list", {"project_id": PROJECT_ID})
        data = _data(result)
        assert "specs" in data

    @pytest.mark.anyio
    async def test_spec_transition(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Transition Test", "description": "test"},
        )
        spec_id = _data(create_result)["spec_id"]
        result = await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "READY", "agent_role": "architect"},
        )
        assert _data(result)["success"] is True

    @pytest.mark.anyio
    async def test_spec_update(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Update Test", "description": "test"},
        )
        spec_id = _data(create_result)["spec_id"]
        result = await server.call_tool(
            "spec_update",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "fields": {"retry_count": 1}},
        )
        assert _data(result)["success"] is True

    @pytest.mark.anyio
    async def test_spec_write_feedback(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Feedback Test", "description": "test"},
        )
        spec_id = _data(create_result)["spec_id"]
        result = await server.call_tool(
            "spec_write_feedback",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "verdict": "ACCEPT", "feedback": "Looks good"},
        )
        assert "path" in _data(result)

    @pytest.mark.anyio
    async def test_sentinel_check_write(self, server: FastMCP, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(yaml.dump({"write_set": ["src/**/*.py"]}))
        result = await server.call_tool(
            "sentinel_check_write",
            {"project_id": PROJECT_ID, "file_path": "src/auth.py", "agent_role": "worker"},
        )
        assert _data(result)["allowed"] is True

    @pytest.mark.anyio
    async def test_run_command_checked(self, server: FastMCP, project_dir: Path) -> None:
        """AC-I7: Async tool callable via call_tool."""
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(yaml.dump({"command_allowlist": ["echo"]}))
        result = await server.call_tool(
            "run_command_checked",
            {"project_id": PROJECT_ID, "command": "echo hello", "agent_role": "worker"},
        )
        data = _data(result)
        assert data["allowed"] is True
        assert data["exit_code"] == 0

    @pytest.mark.anyio
    async def test_web_fetch_checked(self, server: FastMCP) -> None:
        """AC-I7: Async tool callable via call_tool."""
        with patch("vizier_mcp.tools.sentinel.httpx.AsyncClient") as mock_client_cls:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "Clean content"
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            result = await server.call_tool(
                "web_fetch_checked",
                {"url": "https://example.com", "agent_role": "worker"},
            )
            assert _data(result)["safe"] is True

    @pytest.mark.anyio
    async def test_orch_write_ping(self, server: FastMCP, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        result = await server.call_tool(
            "orch_write_ping",
            {"project_id": PROJECT_ID, "spec_id": "001-test", "urgency": "QUESTION", "message": "Help?"},
        )
        assert _data(result)["written"] is True

    @pytest.mark.anyio
    async def test_project_get_config(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("project_get_config", {"project_id": PROJECT_ID})
        data = _data(result)
        assert data["type"] is None
        assert data["settings"] == {}


class TestEndToEndHappyPath:
    """End-to-end test: DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE (AC-I3)."""

    @pytest.mark.anyio
    async def test_happy_path_lifecycle(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "E2E Happy Path", "description": "Testing full lifecycle"},
        )
        spec_id = _data(create_result)["spec_id"]

        for new_status, role in [("READY", "architect"), ("IN_PROGRESS", "pasha"), ("REVIEW", "worker")]:
            result = await server.call_tool(
                "spec_transition",
                {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": new_status, "agent_role": role},
            )
            assert _data(result)["success"] is True

        fb_result = await server.call_tool(
            "spec_write_feedback",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "verdict": "ACCEPT", "feedback": "All good"},
        )
        assert "path" in _data(fb_result)

        done_result = await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "DONE", "agent_role": "quality_gate"},
        )
        assert _data(done_result)["success"] is True

        read_result = await server.call_tool("spec_read", {"project_id": PROJECT_ID, "spec_id": spec_id})
        assert _data(read_result)["metadata"]["status"] == "DONE"


class TestEndToEndRejection:
    """End-to-end test: rejection -> retry -> DONE (AC-I4)."""

    @pytest.mark.anyio
    async def test_rejection_retry_lifecycle(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "E2E Rejection", "description": "Testing rejection path"},
        )
        spec_id = _data(create_result)["spec_id"]

        for new_status, role in [("READY", "architect"), ("IN_PROGRESS", "pasha"), ("REVIEW", "worker")]:
            await server.call_tool(
                "spec_transition",
                {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": new_status, "agent_role": role},
            )

        await server.call_tool(
            "spec_write_feedback",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "verdict": "REJECT", "feedback": "Needs more tests"},
        )
        reject_result = await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "REJECTED", "agent_role": "quality_gate"},
        )
        assert _data(reject_result)["success"] is True

        for new_status, role in [("READY", "architect"), ("IN_PROGRESS", "pasha"), ("REVIEW", "worker")]:
            await server.call_tool(
                "spec_transition",
                {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": new_status, "agent_role": role},
            )

        await server.call_tool(
            "spec_write_feedback",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "verdict": "ACCEPT", "feedback": "Better now"},
        )
        done_result = await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "DONE", "agent_role": "quality_gate"},
        )
        assert _data(done_result)["success"] is True

        read_result = await server.call_tool("spec_read", {"project_id": PROJECT_ID, "spec_id": spec_id})
        data = _data(read_result)
        assert data["metadata"]["status"] == "DONE"
        assert data["metadata"]["retry_count"] == 1


class TestEndToEndStuck:
    """End-to-end test: spec reaches STUCK (AC-I5)."""

    @pytest.mark.anyio
    async def test_stuck_escalation(self, server: FastMCP, project_dir: Path) -> None:
        create_result = await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "E2E Stuck", "description": "Testing stuck path"},
        )
        spec_id = _data(create_result)["spec_id"]

        await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "READY", "agent_role": "architect"},
        )

        stuck_result = await server.call_tool(
            "spec_transition",
            {"project_id": PROJECT_ID, "spec_id": spec_id, "new_status": "STUCK", "agent_role": "pasha"},
        )
        assert _data(stuck_result)["success"] is True

        read_result = await server.call_tool("spec_read", {"project_id": PROJECT_ID, "spec_id": spec_id})
        assert _data(read_result)["metadata"]["status"] == "STUCK"
