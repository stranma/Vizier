"""Tests for observability MCP tools (Phase 8c, AC-8.4, AC-8.5, AC-8.6)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.tools.observability import system_get_errors, system_get_logs


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def slog(log_dir: Path) -> StructuredLogger:
    return StructuredLogger(log_dir)


class TestSystemGetLogs:
    """Tests for system_get_logs (AC-8.4)."""

    def test_returns_recent_entries(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"tool": "spec_create"})
        slog.log("ERROR", "server", "tool_error", {"tool": "spec_read"})
        result = system_get_logs(slog, since_minutes=5)
        assert "entries" in result
        assert "total_matched" in result
        assert "truncated" in result
        assert result["total_matched"] == 2

    def test_filter_by_level(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        slog.log("ERROR", "server", "tool_error", {})
        result = system_get_logs(slog, level="ERROR", since_minutes=5)
        assert result["total_matched"] == 1

    def test_filter_by_event(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        slog.log("INFO", "server", "spec_transition", {})
        result = system_get_logs(slog, event="tool_call", since_minutes=5)
        assert result["total_matched"] == 1

    def test_empty_log(self, slog: StructuredLogger) -> None:
        result = system_get_logs(slog, since_minutes=5)
        assert result["entries"] == []
        assert result["total_matched"] == 0

    def test_all_filters_combined(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"spec_id": "001-auth"})
        slog.log("INFO", "sentinel", "sentinel_decision", {"spec_id": "001-auth"})
        slog.log("ERROR", "server", "tool_error", {"spec_id": "002-db"})
        result = system_get_logs(
            slog, level="INFO", module="server", event="tool_call", spec_id="001-auth", since_minutes=5
        )
        assert result["total_matched"] == 1


class TestSystemGetErrors:
    """Tests for system_get_errors (AC-8.5)."""

    def test_returns_errors_only(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        slog.log("ERROR", "server", "tool_error", {"tool": "broken"})
        slog.log("ERROR", "sentinel", "sentinel_decision", {"denied": True})
        result = system_get_errors(slog, since_minutes=5)
        assert "errors" in result
        assert "total" in result
        assert result["total"] == 2

    def test_no_errors(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        result = system_get_errors(slog, since_minutes=5)
        assert result["errors"] == []
        assert result["total"] == 0

    def test_respects_limit(self, slog: StructuredLogger) -> None:
        for i in range(10):
            slog.log("ERROR", "server", "tool_error", {"i": i})
        result = system_get_errors(slog, since_minutes=5, limit=3)
        assert len(result["errors"]) == 3
        assert result["total"] == 10
