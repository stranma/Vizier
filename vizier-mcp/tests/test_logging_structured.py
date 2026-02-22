"""Tests for structured JSONL logging (Phase 8b, AC-8.2, AC-8.3)."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from vizier_mcp.logging_structured import StructuredLogger


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    """Create a temporary log directory."""
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def slog(log_dir: Path) -> StructuredLogger:
    """Create a StructuredLogger with small rotation for testing."""
    return StructuredLogger(log_dir, max_size_bytes=500, max_files=3)


class TestStructuredLogger:
    """Tests for basic logging operations."""

    def test_log_creates_file(self, slog: StructuredLogger, log_dir: Path) -> None:
        slog.log("INFO", "server", "system_startup", {"version": "0.8.0"})
        assert slog.log_path.exists()

    def test_log_entry_format(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"tool": "spec_create"})
        with open(slog.log_path) as f:
            entry = json.loads(f.readline())
        assert "timestamp" in entry
        assert entry["level"] == "INFO"
        assert entry["module"] == "server"
        assert entry["event"] == "tool_call"
        assert entry["data"]["tool"] == "spec_create"

    def test_log_tool_call(self, slog: StructuredLogger) -> None:
        slog.log_tool_call("spec_create", 12.5, success=True)
        with open(slog.log_path) as f:
            entry = json.loads(f.readline())
        assert entry["event"] == "tool_call"
        assert entry["data"]["tool"] == "spec_create"
        assert entry["data"]["duration_ms"] == 12.5
        assert entry["data"]["success"] is True

    def test_log_tool_error(self, slog: StructuredLogger) -> None:
        slog.log_tool_call("spec_read", 5.0, success=False, data={"error": "Not found"})
        with open(slog.log_path) as f:
            entry = json.loads(f.readline())
        assert entry["level"] == "ERROR"
        assert entry["event"] == "tool_error"
        assert entry["data"]["error"] == "Not found"

    def test_multiple_entries(self, log_dir: Path) -> None:
        large_slog = StructuredLogger(log_dir, max_size_bytes=1024 * 1024)
        for i in range(5):
            large_slog.log("INFO", "server", "tool_call", {"tool": f"tool_{i}"})
        with open(large_slog.log_path) as f:
            lines = [line for line in f if line.strip()]
        assert len(lines) == 5


class TestLogRotation:
    """Tests for log rotation (AC-8.3)."""

    def test_rotation_creates_numbered_files(self, slog: StructuredLogger, log_dir: Path) -> None:
        for i in range(50):
            slog.log("INFO", "server", "tool_call", {"tool": f"tool_{i}", "padding": "x" * 50})
        rotated = log_dir / "vizier-mcp.jsonl.1"
        assert rotated.exists()

    def test_rotation_keeps_max_files(self, log_dir: Path) -> None:
        slog = StructuredLogger(log_dir, max_size_bytes=100, max_files=2)
        for i in range(200):
            slog.log("INFO", "server", "tool_call", {"i": i})
        assert (log_dir / "vizier-mcp.jsonl").exists()
        assert not (log_dir / "vizier-mcp.jsonl.3").exists()

    def test_active_file_stays_small(self, slog: StructuredLogger) -> None:
        for i in range(100):
            slog.log("INFO", "server", "tool_call", {"i": i, "padding": "x" * 50})
        assert slog.log_path.stat().st_size < slog._max_size_bytes * 2


class TestReadEntries:
    """Tests for log reading and filtering (AC-8.4, AC-8.5)."""

    def test_read_recent_entries(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"tool": "spec_create"})
        slog.log("ERROR", "server", "tool_error", {"tool": "spec_read"})
        result = slog.read_entries(since_minutes=5)
        assert result["total_matched"] == 2
        assert len(result["entries"]) == 2
        assert result["truncated"] is False

    def test_filter_by_level(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"tool": "a"})
        slog.log("ERROR", "server", "tool_error", {"tool": "b"})
        slog.log("INFO", "server", "tool_call", {"tool": "c"})
        result = slog.read_entries(level="ERROR", since_minutes=5)
        assert result["total_matched"] == 1
        assert result["entries"][0]["data"]["tool"] == "b"

    def test_filter_by_module(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        slog.log("INFO", "sentinel", "sentinel_decision", {})
        result = slog.read_entries(module="sentinel", since_minutes=5)
        assert result["total_matched"] == 1

    def test_filter_by_event(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {})
        slog.log("INFO", "server", "spec_transition", {})
        result = slog.read_entries(event="spec_transition", since_minutes=5)
        assert result["total_matched"] == 1

    def test_filter_by_spec_id(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"spec_id": "001-auth"})
        slog.log("INFO", "server", "tool_call", {"spec_id": "002-db"})
        result = slog.read_entries(spec_id="001-auth", since_minutes=5)
        assert result["total_matched"] == 1

    def test_limit_and_truncation(self, slog: StructuredLogger) -> None:
        for i in range(10):
            slog.log("INFO", "server", "tool_call", {"i": i})
        result = slog.read_entries(since_minutes=5, limit=3)
        assert len(result["entries"]) == 3
        assert result["total_matched"] == 10
        assert result["truncated"] is True

    def test_newest_first_ordering(self, slog: StructuredLogger) -> None:
        slog.log("INFO", "server", "tool_call", {"order": "first"})
        time.sleep(0.01)
        slog.log("INFO", "server", "tool_call", {"order": "second"})
        result = slog.read_entries(since_minutes=5)
        assert result["entries"][0]["data"]["order"] == "second"

    def test_empty_log_returns_empty_list(self, slog: StructuredLogger) -> None:
        result = slog.read_entries(since_minutes=5)
        assert result["entries"] == []
        assert result["total_matched"] == 0
        assert result["truncated"] is False

    def test_reads_from_rotated_files(self, slog: StructuredLogger) -> None:
        for i in range(50):
            slog.log("INFO", "server", "tool_call", {"i": i, "padding": "x" * 50})
        result = slog.read_entries(since_minutes=5, limit=200)
        assert result["total_matched"] >= 10
