"""Tests for system_get_status MCP tool (Phase 9a, AC-9.1, AC-9.2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.tools.spec import spec_create, spec_transition
from vizier_mcp.tools.status import system_get_status

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


@pytest.fixture
def slog(config: ServerConfig) -> StructuredLogger:
    assert config.log_dir is not None
    return StructuredLogger(config.log_dir)


class TestSystemGetStatus:
    """Tests for system_get_status (AC-9.1)."""

    def test_returns_server_info(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        result = system_get_status(config, slog, "0.9.0", 16)
        assert result["server"]["version"] == "0.9.0"
        assert result["server"]["tool_count"] == 16
        assert "uptime_seconds" in result["server"]

    def test_returns_spec_counts_by_status(
        self, config: ServerConfig, slog: StructuredLogger, project_dir: Path
    ) -> None:
        spec_create(config, PROJECT_ID, "Spec A", "desc")
        result_create = spec_create(config, PROJECT_ID, "Spec B", "desc")
        spec_transition(config, PROJECT_ID, result_create["spec_id"], "READY", "architect")

        result = system_get_status(config, slog, "0.9.0", 16)
        by_status = result["specs"]["by_status"]
        assert by_status["DRAFT"] == 1
        assert by_status["READY"] == 1

    def test_stuck_specs_listed_with_timing(
        self, config: ServerConfig, slog: StructuredLogger, project_dir: Path
    ) -> None:
        cr = spec_create(config, PROJECT_ID, "Stuck Spec", "desc")
        spec_id = cr["spec_id"]
        spec_transition(config, PROJECT_ID, spec_id, "READY", "architect")
        spec_transition(config, PROJECT_ID, spec_id, "STUCK", "pasha")

        result = system_get_status(config, slog, "0.9.0", 16)
        stuck = result["specs"]["stuck"]
        assert len(stuck) == 1
        assert stuck[0]["spec_id"] == spec_id
        assert "age_minutes" in stuck[0]
        assert "stuck_since" in stuck[0]

    def test_in_progress_specs_listed(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        cr = spec_create(config, PROJECT_ID, "WIP Spec", "desc")
        spec_id = cr["spec_id"]
        spec_transition(config, PROJECT_ID, spec_id, "READY", "architect")
        spec_transition(config, PROJECT_ID, spec_id, "IN_PROGRESS", "pasha")

        result = system_get_status(config, slog, "0.9.0", 16)
        in_progress = result["specs"]["in_progress"]
        assert len(in_progress) == 1
        assert in_progress[0]["spec_id"] == spec_id
        assert "age_minutes" in in_progress[0]

    def test_recent_activity_section(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        result = system_get_status(config, slog, "0.9.0", 16)
        activity = result["recent_activity"]
        assert "transitions_1h" in activity
        assert "errors_1h" in activity
        assert "sentinel_denials_1h" in activity

    def test_empty_project_returns_zeroes(
        self, config: ServerConfig, slog: StructuredLogger, project_dir: Path
    ) -> None:
        result = system_get_status(config, slog, "0.9.0", 16)
        by_status = result["specs"]["by_status"]
        assert all(v == 0 for v in by_status.values())
        assert result["specs"]["stuck"] == []
        assert result["specs"]["in_progress"] == []


class TestSystemGetStatusProjectFilter:
    """Tests for project_id filtering (AC-9.2)."""

    def test_filter_by_project(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        spec_create(config, PROJECT_ID, "Project Spec", "desc")
        result = system_get_status(config, slog, "0.9.0", 16, project_id=PROJECT_ID)
        assert result["specs"]["by_status"]["DRAFT"] == 1

    def test_nonexistent_project_returns_zeroes(
        self, config: ServerConfig, slog: StructuredLogger, project_dir: Path
    ) -> None:
        result = system_get_status(config, slog, "0.9.0", 16, project_id="nonexistent")
        by_status = result["specs"]["by_status"]
        assert all(v == 0 for v in by_status.values())
