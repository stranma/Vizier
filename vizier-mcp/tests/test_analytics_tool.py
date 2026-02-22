"""Tests for spec_analytics MCP tool (Phase 9b, AC-9.3)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.tools.analytics import spec_analytics
from vizier_mcp.tools.spec import spec_create, spec_transition, spec_write_feedback

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


@pytest.fixture
def slog(config: ServerConfig) -> StructuredLogger:
    assert config.log_dir is not None
    return StructuredLogger(config.log_dir)


class TestSpecAnalytics:
    """Tests for spec_analytics (AC-9.3)."""

    def test_no_specs_returns_zeroes(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        result = spec_analytics(config, slog, PROJECT_ID)
        assert result["project_id"] == PROJECT_ID
        assert result["total_specs"] == 0
        assert result["throughput"]["completed"] == 0
        assert result["throughput"]["success_rate"] == 0.0
        assert result["timing"]["avg_time_to_done_minutes"] == 0.0
        assert result["quality"]["rejection_count"] == 0
        assert result["quality"]["avg_retries"] == 0.0

    def test_throughput_counts(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        cr1 = spec_create(config, PROJECT_ID, "Done Spec", "desc")
        spec_transition(config, PROJECT_ID, cr1["spec_id"], "READY", "architect")
        spec_transition(config, PROJECT_ID, cr1["spec_id"], "IN_PROGRESS", "pasha")
        spec_transition(config, PROJECT_ID, cr1["spec_id"], "REVIEW", "worker")
        spec_write_feedback(config, PROJECT_ID, cr1["spec_id"], "ACCEPT", "Good")
        spec_transition(config, PROJECT_ID, cr1["spec_id"], "DONE", "quality_gate")

        cr2 = spec_create(config, PROJECT_ID, "Stuck Spec", "desc")
        spec_transition(config, PROJECT_ID, cr2["spec_id"], "READY", "architect")
        spec_transition(config, PROJECT_ID, cr2["spec_id"], "STUCK", "pasha")

        spec_create(config, PROJECT_ID, "Draft Spec", "desc")

        result = spec_analytics(config, slog, PROJECT_ID)
        assert result["total_specs"] == 3
        assert result["throughput"]["completed"] == 1
        assert result["throughput"]["stuck"] == 1
        assert result["throughput"]["total"] == 3

    def test_quality_metrics(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        cr = spec_create(config, PROJECT_ID, "Rejected Spec", "desc")
        sid = cr["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "architect")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "pasha")
        spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")
        spec_write_feedback(config, PROJECT_ID, sid, "REJECT", "Bad code")
        spec_transition(config, PROJECT_ID, sid, "REJECTED", "quality_gate")
        spec_transition(config, PROJECT_ID, sid, "READY", "architect")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "pasha")
        spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")
        spec_write_feedback(config, PROJECT_ID, sid, "ACCEPT", "Fixed")
        spec_transition(config, PROJECT_ID, sid, "DONE", "quality_gate")

        result = spec_analytics(config, slog, PROJECT_ID)
        assert result["quality"]["rejection_count"] == 1
        assert result["quality"]["total_retries"] == 1
        assert result["quality"]["specs_with_retries"] == 1

    def test_timing_with_done_spec(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        cr = spec_create(config, PROJECT_ID, "Timed Spec", "desc")
        sid = cr["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "architect")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "pasha")
        spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")
        spec_write_feedback(config, PROJECT_ID, sid, "ACCEPT", "OK")
        spec_transition(config, PROJECT_ID, sid, "DONE", "quality_gate")

        result = spec_analytics(config, slog, PROJECT_ID)
        assert result["timing"]["avg_time_to_done_minutes"] >= 0.0
        assert result["timing"]["slowest_spec"] is not None
        assert result["timing"]["slowest_spec"]["spec_id"] == sid

    def test_sentinel_section_present(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        result = spec_analytics(config, slog, PROJECT_ID)
        assert "sentinel" in result
        assert "total_checks" in result["sentinel"]
        assert "denials" in result["sentinel"]

    def test_success_rate_calculation(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        for title in ["A", "B"]:
            cr = spec_create(config, PROJECT_ID, title, "desc")
            spec_transition(config, PROJECT_ID, cr["spec_id"], "READY", "architect")
            spec_transition(config, PROJECT_ID, cr["spec_id"], "IN_PROGRESS", "pasha")
            spec_transition(config, PROJECT_ID, cr["spec_id"], "REVIEW", "worker")
            spec_write_feedback(config, PROJECT_ID, cr["spec_id"], "ACCEPT", "OK")
            spec_transition(config, PROJECT_ID, cr["spec_id"], "DONE", "quality_gate")

        spec_create(config, PROJECT_ID, "C", "desc")

        result = spec_analytics(config, slog, PROJECT_ID)
        assert result["throughput"]["success_rate"] == round(2 / 3, 2)
