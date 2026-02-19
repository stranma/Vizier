"""Tests for Golden Trace analyzer."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.retrospective.trace_analyzer import (
    analyze_project_traces,
    analyze_trace_file,
    format_trace_summary,
)


class TestAnalyzeTraceFile:
    def test_empty_file(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        trace.write_text("")
        stats = analyze_trace_file(str(trace))
        assert stats.total_tool_calls == 0
        assert stats.specs_analyzed == 1

    def test_nonexistent_file(self) -> None:
        stats = analyze_trace_file("/nonexistent/trace.jsonl")
        assert stats.total_tool_calls == 0

    def test_counts_tool_calls(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        entries = [
            {"tool_name": "read_file", "tool_input": {"path": "a.py"}, "tool_result": {}},
            {"tool_name": "write_file", "tool_input": {"path": "b.py"}, "tool_result": {}},
            {"tool_name": "read_file", "tool_input": {"path": "c.py"}, "tool_result": {}},
        ]
        trace.write_text("\n".join(json.dumps(e) for e in entries))
        stats = analyze_trace_file(str(trace))
        assert stats.total_tool_calls == 3
        assert stats.tool_frequency["read_file"] == 2
        assert stats.tool_frequency["write_file"] == 1

    def test_detects_errors(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        entries = [
            {"tool_name": "bash", "tool_input": {}, "tool_result": {"error": "timeout"}},
            {"tool_name": "read_file", "tool_input": {}, "tool_result": {"content": "ok"}},
        ]
        trace.write_text("\n".join(json.dumps(e) for e in entries))
        stats = analyze_trace_file(str(trace))
        assert stats.error_count == 1

    def test_detects_sentinel_deny(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        entries = [
            {"tool_name": "write_file", "tool_input": {}, "sentinel_decision": "DENY", "tool_result": {}},
        ]
        trace.write_text("\n".join(json.dumps(e) for e in entries))
        stats = analyze_trace_file(str(trace))
        assert stats.error_count == 1

    def test_detects_repeated_calls(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        entry = {"tool_name": "bash", "tool_input": {"command": "pytest"}, "tool_result": {}}
        trace.write_text("\n".join(json.dumps(entry) for _ in range(3)))
        stats = analyze_trace_file(str(trace))
        assert stats.repeated_calls == 2

    def test_detects_escalations(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        entries = [
            {"tool_name": "escalate_to_pasha", "tool_input": {}, "tool_result": {}},
            {"tool_name": "read_file", "tool_input": {}, "tool_result": {}},
        ]
        trace.write_text("\n".join(json.dumps(e) for e in entries))
        stats = analyze_trace_file(str(trace))
        assert stats.escalation_count == 1

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        trace = tmp_path / "trace.jsonl"
        trace.write_text('{"tool_name": "read_file"}\n{invalid\n{"tool_name": "glob"}')
        stats = analyze_trace_file(str(trace))
        assert stats.total_tool_calls == 2


class TestAnalyzeProjectTraces:
    def test_empty_project(self, tmp_path: Path) -> None:
        stats = analyze_project_traces(str(tmp_path))
        assert stats.specs_analyzed == 0

    def test_aggregates_across_specs(self, tmp_path: Path) -> None:
        for spec_id in ["001", "002"]:
            spec_dir = tmp_path / ".vizier" / "specs" / spec_id
            spec_dir.mkdir(parents=True)
            entry = {"tool_name": "read_file", "tool_input": {}, "tool_result": {}}
            (spec_dir / "trace.jsonl").write_text(json.dumps(entry))

        stats = analyze_project_traces(str(tmp_path))
        assert stats.specs_analyzed == 2
        assert stats.total_tool_calls == 2


class TestFormatTraceSummary:
    def test_empty_stats(self) -> None:
        from vizier.core.agents.retrospective.trace_analyzer import TraceStats

        stats = TraceStats()
        summary = format_trace_summary(stats)
        assert "Specs analyzed: 0" in summary

    def test_with_data(self) -> None:
        from vizier.core.agents.retrospective.trace_analyzer import TraceStats

        stats = TraceStats(
            total_tool_calls=100,
            error_count=5,
            tool_frequency={"read_file": 60, "bash": 40},
            repeated_calls=3,
            specs_analyzed=10,
            escalation_count=2,
        )
        summary = format_trace_summary(stats)
        assert "100" in summary
        assert "5.0%" in summary
        assert "read_file: 60" in summary
