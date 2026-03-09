"""Tests for audit interceptor and query tools (Phase 13: Imperial Observability).

Tests AuditLogger, audit_query, audit_timeline, and audit_stats tools,
including automatic interception of existing tool calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vizier_mcp.audit_logger import AuditLogger
from vizier_mcp.models.audit import AuditEntry
from vizier_mcp.server import TOOL_COUNT, create_server
from vizier_mcp.tools.audit import audit_query, audit_stats, audit_timeline

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import FastMCP

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"
SPEC_ID = "001-auth"


@pytest.fixture
def audit_logger(config: ServerConfig) -> AuditLogger:
    """Create an AuditLogger for testing."""
    assert config.audit_dir is not None
    assert config.projects_dir is not None
    return AuditLogger(config.audit_dir, config.projects_dir)


def _make_entry(
    tool_name: str = "spec_read",
    project_id: str = PROJECT_ID,
    spec_id: str = SPEC_ID,
    agent_role: str = "worker",
    success: bool = True,
    duration_ms: float = 10.0,
) -> AuditEntry:
    """Create a test AuditEntry."""
    return AuditEntry(
        tool_name=tool_name,
        kwargs={"project_id": project_id, "spec_id": spec_id},
        result={"status": "ok"},
        success=success,
        duration_ms=duration_ms,
        project_id=project_id,
        spec_id=spec_id,
        agent_role=agent_role,
    )


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_record_creates_global_log(self, audit_logger: AuditLogger) -> None:
        entry = _make_entry()
        audit_logger.record(entry)
        assert audit_logger.global_log_path.exists()

    def test_record_creates_per_spec_log(self, audit_logger: AuditLogger, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        entry = _make_entry()
        audit_logger.record(entry)
        per_spec_path = spec_dir / ".vizier" / "audit.jsonl"
        assert per_spec_path.exists()

    def test_no_per_spec_without_ids(self, audit_logger: AuditLogger) -> None:
        entry = _make_entry(project_id="", spec_id="")
        audit_logger.record(entry)
        assert audit_logger.global_log_path.exists()

    def test_multiple_entries(self, audit_logger: AuditLogger) -> None:
        for i in range(5):
            audit_logger.record(_make_entry(duration_ms=float(i)))
        entries = audit_logger.read_entries()
        assert len(entries) == 5

    def test_build_entry_extracts_context(self, audit_logger: AuditLogger) -> None:
        kwargs: dict[str, Any] = {"project_id": "proj1", "spec_id": "spec1", "agent_role": "worker"}
        entry = audit_logger.build_entry("spec_read", kwargs, {"data": "ok"}, True, "", 15.5)
        assert entry.project_id == "proj1"
        assert entry.spec_id == "spec1"
        assert entry.agent_role == "worker"
        assert entry.duration_ms == 15.5

    def test_truncate_large_result(self, audit_logger: AuditLogger) -> None:
        large_result = {"stdout": "x" * 10000}
        entry = audit_logger.build_entry("run_cmd", {}, large_result, True, "", 1.0)
        assert len(entry.result["stdout"]) < 10000
        assert "truncated" in entry.result["stdout"]

    def test_read_entries_filter_by_tool(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry(tool_name="spec_read"))
        audit_logger.record(_make_entry(tool_name="spec_create"))
        audit_logger.record(_make_entry(tool_name="spec_read"))
        entries = audit_logger.read_entries(tool_name="spec_read")
        assert len(entries) == 2

    def test_read_entries_filter_by_agent(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry(agent_role="worker"))
        audit_logger.record(_make_entry(agent_role="quality_gate"))
        entries = audit_logger.read_entries(agent_role="quality_gate")
        assert len(entries) == 1

    def test_read_entries_limit(self, audit_logger: AuditLogger) -> None:
        for _ in range(10):
            audit_logger.record(_make_entry())
        entries = audit_logger.read_entries(limit=3)
        assert len(entries) == 3


class TestAuditQuery:
    """Tests for audit_query tool."""

    def test_empty(self, audit_logger: AuditLogger) -> None:
        result = audit_query(audit_logger)
        assert result["entries"] == []
        assert result["total"] == 0

    def test_returns_entries(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry())
        audit_logger.record(_make_entry())
        result = audit_query(audit_logger)
        assert result["total"] == 2

    def test_filter_by_tool(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry(tool_name="spec_read"))
        audit_logger.record(_make_entry(tool_name="spec_create"))
        result = audit_query(audit_logger, tool_name="spec_create")
        assert result["total"] == 1


class TestAuditTimeline:
    """Tests for audit_timeline tool."""

    def test_empty(self, audit_logger: AuditLogger, project_dir: Path) -> None:
        result = audit_timeline(audit_logger, PROJECT_ID, "nonexistent")
        assert result["timeline"] == []
        assert result["total_calls"] == 0

    def test_chronological(self, audit_logger: AuditLogger, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        audit_logger.record(_make_entry(tool_name="spec_read", duration_ms=1.0))
        audit_logger.record(_make_entry(tool_name="sentinel_check_write", duration_ms=2.0))
        audit_logger.record(_make_entry(tool_name="spec_transition", duration_ms=3.0))
        result = audit_timeline(audit_logger, PROJECT_ID, SPEC_ID)
        assert result["total_calls"] == 3
        assert result["timeline"][0]["tool"] == "spec_read"
        assert result["timeline"][2]["tool"] == "spec_transition"

    def test_agents_list(self, audit_logger: AuditLogger, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        audit_logger.record(_make_entry(agent_role="worker"))
        audit_logger.record(_make_entry(agent_role="quality_gate"))
        result = audit_timeline(audit_logger, PROJECT_ID, SPEC_ID)
        assert sorted(result["agents"]) == ["quality_gate", "worker"]


class TestAuditStats:
    """Tests for audit_stats tool."""

    def test_empty(self, audit_logger: AuditLogger) -> None:
        result = audit_stats(audit_logger)
        assert result["total_calls"] == 0
        assert result["error_count"] == 0

    def test_counts(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry(tool_name="spec_read"))
        audit_logger.record(_make_entry(tool_name="spec_read"))
        audit_logger.record(_make_entry(tool_name="spec_create"))
        audit_logger.record(_make_entry(tool_name="spec_read", success=False))
        result = audit_stats(audit_logger)
        assert result["total_calls"] == 4
        assert result["error_count"] == 1
        assert result["by_tool"]["spec_read"] == 3
        assert result["by_tool"]["spec_create"] == 1

    def test_agent_breakdown(self, audit_logger: AuditLogger) -> None:
        audit_logger.record(_make_entry(agent_role="worker"))
        audit_logger.record(_make_entry(agent_role="worker"))
        audit_logger.record(_make_entry(agent_role="pasha"))
        result = audit_stats(audit_logger)
        assert result["by_agent"]["worker"] == 2
        assert result["by_agent"]["pasha"] == 1


class TestAuditInterception:
    """Tests that calling existing tools automatically produces audit entries."""

    @pytest.fixture
    def server(self, config: ServerConfig) -> FastMCP:
        """Create a FastMCP server with test config."""
        return create_server(config)

    @pytest.mark.anyio
    async def test_spec_create_produces_audit(self, server: FastMCP, project_dir: Path, config: ServerConfig) -> None:
        await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Audit Test", "description": "test"},
        )
        assert config.audit_dir is not None
        audit_file = config.audit_dir / "audit.jsonl"
        assert audit_file.exists()
        import json

        lines = [ln for ln in audit_file.read_text().splitlines() if ln.strip()]
        found = False
        for line in lines:
            data = json.loads(line)
            if data["tool_name"] == "spec_create":
                found = True
                assert data["success"] is True
                assert data["project_id"] == PROJECT_ID
        assert found

    @pytest.mark.anyio
    async def test_audit_query_via_server(self, server: FastMCP, project_dir: Path) -> None:
        await server.call_tool(
            "spec_create",
            {"project_id": PROJECT_ID, "title": "Query Test", "description": "test"},
        )
        result = await server.call_tool(
            "audit_query",
            {"project_id": PROJECT_ID, "limit": 10},
        )
        data = result.structured_content  # type: ignore[union-attr]
        assert data is not None
        assert data["total"] >= 1

    @pytest.mark.anyio
    async def test_tool_count_is_28(self) -> None:
        assert TOOL_COUNT == 28
