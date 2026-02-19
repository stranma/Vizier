"""Tests for TraceLogger (Golden Trace D57)."""

import json
from pathlib import Path

from vizier.core.runtime.trace import TraceLogger


class TestTraceLogger:
    def test_in_memory_only(self) -> None:
        trace = TraceLogger()
        trace.log("run_start", {"task": "test"})
        assert len(trace.entries) == 1
        assert trace.entries[0]["event"] == "run_start"
        assert trace.entries[0]["task"] == "test"
        assert "timestamp" in trace.entries[0]

    def test_multiple_entries(self) -> None:
        trace = TraceLogger()
        trace.log("start")
        trace.log("tool_call", {"tool": "read_file"})
        trace.log("end")
        assert len(trace.entries) == 3
        assert [e["event"] for e in trace.entries] == ["start", "tool_call", "end"]

    def test_no_data(self) -> None:
        trace = TraceLogger()
        trace.log("simple_event")
        assert trace.entries[0]["event"] == "simple_event"
        assert "timestamp" in trace.entries[0]

    def test_file_output(self, tmp_path: Path) -> None:
        trace_file = tmp_path / "specs" / "001" / "trace.jsonl"
        trace = TraceLogger(trace_path=trace_file)
        trace.log("run_start", {"model": "sonnet"})
        trace.log("tool_call", {"tool": "bash"})

        assert trace_file.exists()
        lines = trace_file.read_text().strip().split("\n")
        assert len(lines) == 2

        entry1 = json.loads(lines[0])
        assert entry1["event"] == "run_start"
        assert entry1["model"] == "sonnet"

        entry2 = json.loads(lines[1])
        assert entry2["event"] == "tool_call"

    def test_entries_returns_copy(self) -> None:
        trace = TraceLogger()
        trace.log("test")
        entries = trace.entries
        entries.clear()
        assert len(trace.entries) == 1
