"""Tests for FastMCP server integration (Phase 4, updated Phase 13).

Tests that all tools are registered and callable via call_tool,
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
    "secret_check",
    "system_get_logs",
    "system_get_errors",
    "system_get_status",
    "spec_analytics",
    "budget_record",
    "budget_summary",
    "learnings_extract",
    "learnings_list",
    "learnings_inject",
    "audit_query",
    "audit_timeline",
    "audit_stats",
    "trace_record",
    "trace_query",
    "trace_timeline",
    "project_init",
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
        assert TOOL_COUNT == 28


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
    async def test_web_fetch_checked(self, server: FastMCP, project_dir: Path) -> None:
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
                {"project_id": PROJECT_ID, "url": "https://example.com", "agent_role": "worker"},
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

    @pytest.mark.anyio
    async def test_secret_check(self, server: FastMCP) -> None:
        with patch("vizier_mcp.tools.sentinel.get_secret", return_value=None):
            result = await server.call_tool("secret_check", {"name": "SOME_SECRET"})
            data = _data(result)
            assert data["name"] == "SOME_SECRET"
            assert data["exists"] is False

    @pytest.mark.anyio
    async def test_system_get_logs(self, server: FastMCP) -> None:
        result = await server.call_tool("system_get_logs", {"since_minutes": 5})
        data = _data(result)
        assert "entries" in data
        assert "total_matched" in data
        assert "truncated" in data

    @pytest.mark.anyio
    async def test_system_get_errors(self, server: FastMCP) -> None:
        result = await server.call_tool("system_get_errors", {"since_minutes": 5})
        data = _data(result)
        assert "errors" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_system_get_status(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("system_get_status", {})
        data = _data(result)
        assert "server" in data
        assert "specs" in data
        assert "recent_activity" in data

    @pytest.mark.anyio
    async def test_spec_analytics(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("spec_analytics", {"project_id": PROJECT_ID})
        data = _data(result)
        assert data["project_id"] == PROJECT_ID
        assert "throughput" in data
        assert "timing" in data
        assert "quality" in data
        assert "sentinel" in data

    @pytest.mark.anyio
    async def test_budget_record(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool(
            "budget_record",
            {"project_id": PROJECT_ID, "event_type": "haiku_eval", "cost_estimate": 0.001},
        )
        assert _data(result)["recorded"] is True

    @pytest.mark.anyio
    async def test_budget_summary(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("budget_summary", {"project_id": PROJECT_ID})
        data = _data(result)
        assert data["project_id"] == PROJECT_ID
        assert "total_cost" in data

    @pytest.mark.anyio
    async def test_learnings_extract(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("learnings_extract", {"project_id": PROJECT_ID})
        data = _data(result)
        assert "extracted" in data

    @pytest.mark.anyio
    async def test_learnings_list(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("learnings_list", {"project_id": PROJECT_ID})
        data = _data(result)
        assert "learnings" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_learnings_inject(self, server: FastMCP, project_dir: Path) -> None:
        import yaml as _yaml

        spec_dir = project_dir / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        meta = {
            "spec_id": "001-test",
            "project_id": PROJECT_ID,
            "title": "Test",
            "status": "READY",
            "complexity": "MEDIUM",
            "retry_count": 0,
        }
        (spec_dir / "spec.md").write_text(f"---\n{_yaml.dump(meta)}---\nBody\n")
        result = await server.call_tool("learnings_inject", {"project_id": PROJECT_ID, "spec_id": "001-test"})
        data = _data(result)
        assert "matches" in data
        assert "context_text" in data

    @pytest.mark.anyio
    async def test_audit_query(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("audit_query", {"limit": 10})
        data = _data(result)
        assert "entries" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_audit_timeline(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("audit_timeline", {"project_id": PROJECT_ID, "spec_id": "001-test"})
        data = _data(result)
        assert "timeline" in data
        assert "total_calls" in data

    @pytest.mark.anyio
    async def test_audit_stats(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("audit_stats", {})
        data = _data(result)
        assert "total_calls" in data
        assert "by_tool" in data

    @pytest.mark.anyio
    async def test_trace_record(self, server: FastMCP, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-test"
        spec_dir.mkdir(parents=True)
        result = await server.call_tool(
            "trace_record",
            {
                "project_id": PROJECT_ID,
                "spec_id": "001-test",
                "agent_role": "worker",
                "action_type": "reasoning",
                "summary": "Test trace",
            },
        )
        data = _data(result)
        assert data["recorded"] is True

    @pytest.mark.anyio
    async def test_trace_query(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("trace_query", {"project_id": PROJECT_ID, "spec_id": "001-test"})
        data = _data(result)
        assert "entries" in data
        assert "total" in data

    @pytest.mark.anyio
    async def test_trace_timeline(self, server: FastMCP, project_dir: Path) -> None:
        result = await server.call_tool("trace_timeline", {"project_id": PROJECT_ID, "spec_id": "001-test"})
        data = _data(result)
        assert "timeline" in data
        assert "total_entries" in data


class TestToolLogging:
    """Tests for structured logging of tool calls (AC-8.2)."""

    @pytest.mark.anyio
    async def test_tool_call_produces_log_entry(self, server: FastMCP, project_dir: Path, config: ServerConfig) -> None:
        await server.call_tool("spec_list", {"project_id": PROJECT_ID})
        result = await server.call_tool("system_get_logs", {"event": "tool_call", "since_minutes": 1})
        data = _data(result)
        assert data["total_matched"] >= 1
        tools_logged = [e["data"]["tool"] for e in data["entries"] if "tool" in e.get("data", {})]
        assert "spec_list" in tools_logged


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
