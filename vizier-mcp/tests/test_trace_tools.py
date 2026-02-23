"""Tests for Golden Trace tools (Phase 13: Imperial Observability).

Tests trace_record, trace_query, and trace_timeline tools.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vizier_mcp.tools.trace import trace_query, trace_record, trace_timeline

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"
SPEC_ID = "001-auth"


class TestTraceRecord:
    """Tests for trace_record tool."""

    def test_basic_record(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        result = trace_record(config, PROJECT_ID, SPEC_ID, "worker", "decision_made", "Chose REST over GraphQL")
        assert result["recorded"] is True
        assert result["entry"]["action_type"] == "decision_made"
        assert result["entry"]["summary"] == "Chose REST over GraphQL"

    def test_record_with_detail(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        result = trace_record(
            config,
            PROJECT_ID,
            SPEC_ID,
            "worker",
            "reasoning",
            "Analyzing auth options",
            detail="JWT vs session cookies: JWT chosen for stateless API",
        )
        assert result["recorded"] is True
        assert result["entry"]["detail"] == "JWT vs session cookies: JWT chosen for stateless API"

    def test_record_with_metadata(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        meta = {"file": "auth.py", "line": 42}
        result = trace_record(config, PROJECT_ID, SPEC_ID, "worker", "file_written", "Wrote auth module", metadata=meta)
        assert result["recorded"] is True
        assert result["entry"]["metadata"]["file"] == "auth.py"

    def test_missing_required_fields(self, config: ServerConfig, project_dir: Path) -> None:
        result = trace_record(config, "", SPEC_ID, "worker", "reasoning", "test")
        assert "error" in result
        result = trace_record(config, PROJECT_ID, SPEC_ID, "worker", "", "test")
        assert "error" in result

    def test_creates_directory(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "test")
        trace_file = spec_dir / ".vizier" / "trace.jsonl"
        assert trace_file.exists()

    def test_multiple_entries_appended(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Step 1")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "command_executed", "Step 2")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "file_written", "Step 3")
        trace_file = spec_dir / ".vizier" / "trace.jsonl"
        lines = [ln for ln in trace_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            data = json.loads(line)
            assert "action_type" in data


class TestTraceQuery:
    """Tests for trace_query tool."""

    def test_empty_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = trace_query(config, PROJECT_ID, SPEC_ID)
        assert result["entries"] == []
        assert result["total"] == 0

    def test_returns_entries(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Think")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "decision_made", "Decided")
        result = trace_query(config, PROJECT_ID, SPEC_ID)
        assert result["total"] == 2
        assert len(result["entries"]) == 2

    def test_filter_by_action_type(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Think")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "decision_made", "Decided")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Think more")
        result = trace_query(config, PROJECT_ID, SPEC_ID, action_type="reasoning")
        assert result["total"] == 2
        assert all(e["action_type"] == "reasoning" for e in result["entries"])

    def test_filter_by_agent_role(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Worker thought")
        trace_record(config, PROJECT_ID, SPEC_ID, "quality_gate", "test_result", "Tests passed")
        result = trace_query(config, PROJECT_ID, SPEC_ID, agent_role="quality_gate")
        assert result["total"] == 1
        assert result["entries"][0]["agent_role"] == "quality_gate"

    def test_limit(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        for i in range(10):
            trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", f"Step {i}")
        result = trace_query(config, PROJECT_ID, SPEC_ID, limit=3)
        assert len(result["entries"]) == 3
        assert result["total"] == 10


class TestTraceTimeline:
    """Tests for trace_timeline tool."""

    def test_empty_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = trace_timeline(config, PROJECT_ID, SPEC_ID)
        assert result["timeline"] == []
        assert result["total_entries"] == 0

    def test_chronological_order(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Step 1")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "command_executed", "Step 2")
        trace_record(config, PROJECT_ID, SPEC_ID, "quality_gate", "test_result", "Step 3")
        result = trace_timeline(config, PROJECT_ID, SPEC_ID)
        assert result["total_entries"] == 3
        assert result["timeline"][0]["summary"] == "Step 1"
        assert result["timeline"][2]["summary"] == "Step 3"

    def test_agents_summary(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Think")
        trace_record(config, PROJECT_ID, SPEC_ID, "quality_gate", "test_result", "Test")
        result = trace_timeline(config, PROJECT_ID, SPEC_ID)
        assert sorted(result["agents"]) == ["quality_gate", "worker"]

    def test_action_types_summary(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Think")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "file_written", "Write")
        result = trace_timeline(config, PROJECT_ID, SPEC_ID)
        assert sorted(result["action_types"]) == ["file_written", "reasoning"]


class TestTraceIntegration:
    """Integration tests for trace round-trip."""

    def test_record_query_timeline_roundtrip(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / SPEC_ID
        spec_dir.mkdir(parents=True)

        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "reasoning", "Analyzing requirements")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "decision_made", "Using JWT auth")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "file_written", "Created auth.py")
        trace_record(config, PROJECT_ID, SPEC_ID, "worker", "command_executed", "Ran tests")
        trace_record(config, PROJECT_ID, SPEC_ID, "quality_gate", "test_result", "All tests pass")

        query_result = trace_query(config, PROJECT_ID, SPEC_ID)
        assert query_result["total"] == 5

        worker_only = trace_query(config, PROJECT_ID, SPEC_ID, agent_role="worker")
        assert worker_only["total"] == 4

        timeline_result = trace_timeline(config, PROJECT_ID, SPEC_ID)
        assert timeline_result["total_entries"] == 5
        assert len(timeline_result["agents"]) == 2
        assert timeline_result["timeline"][0]["summary"] == "Analyzing requirements"
        assert timeline_result["timeline"][4]["summary"] == "All tests pass"
