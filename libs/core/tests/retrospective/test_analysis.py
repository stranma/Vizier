"""Tests for Retrospective analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vizier.core.file_protocol.spec_io import create_spec, update_spec_status
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.models.logging import AgentLogEntry
from vizier.core.models.spec import SpecStatus
from vizier.core.retrospective.analysis import FailurePattern, RetrospectiveAnalysis, SpecMetrics


def _setup_project(tmp_path: Path) -> Path:
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    (vizier_dir / "constitution.md").write_text("Test constitution.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("No learnings yet.", encoding="utf-8")
    (vizier_dir / "config.yaml").write_text("plugin: software\nproject: test-project\n", encoding="utf-8")
    (vizier_dir / "state.json").write_text(
        json.dumps({"project": "test-project", "plugin": "software"}), encoding="utf-8"
    )
    return tmp_path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return _setup_project(tmp_path)


class TestFailurePattern:
    def test_create_pattern(self) -> None:
        p = FailurePattern(pattern_type="stuck", spec_ids=["s1", "s2"], frequency=2)
        assert p.pattern_type == "stuck"
        assert len(p.spec_ids) == 2

    def test_default_values(self) -> None:
        p = FailurePattern(pattern_type="test")
        assert p.spec_ids == []
        assert p.frequency == 1
        assert p.suggested_action == ""


class TestSpecMetrics:
    def test_defaults(self) -> None:
        m = SpecMetrics()
        assert m.total_specs == 0
        assert m.total_cost_usd == 0.0
        assert m.cost_per_spec == 0.0

    def test_with_values(self) -> None:
        m = SpecMetrics(total_specs=10, done_count=7, stuck_count=1, total_cost_usd=1.5)
        assert m.done_count == 7
        assert m.total_cost_usd == 1.5


class TestFailurePatternDetection:
    def test_no_specs_no_patterns(self, project_root: Path) -> None:
        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        assert len(patterns) == 0

    def test_detects_stuck_specs(self, project_root: Path) -> None:
        spec = create_spec(str(project_root), "stuck-001", "Stuck task", {"status": "READY"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.STUCK)

        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        stuck_patterns = [p for p in patterns if p.pattern_type == "stuck"]
        assert len(stuck_patterns) == 1
        assert "stuck-001" in stuck_patterns[0].spec_ids

    def test_detects_high_retry_specs(self, project_root: Path) -> None:
        create_spec(str(project_root), "retry-001", "Hard task", {"status": "READY", "retries": 5})

        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        retry_patterns = [p for p in patterns if p.pattern_type == "high_retry"]
        assert len(retry_patterns) == 1
        assert "retry-001" in retry_patterns[0].spec_ids

    def test_detects_rejected_specs(self, project_root: Path) -> None:
        spec = create_spec(str(project_root), "rej-001", "Rejected", {"status": "READY"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)
        update_spec_status(spec.file_path, SpecStatus.REJECTED)

        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        rej_patterns = [p for p in patterns if p.pattern_type == "repeated_rejection"]
        assert len(rej_patterns) == 1

    def test_no_false_positives(self, project_root: Path) -> None:
        create_spec(str(project_root), "done-001", "Done", {"status": "READY"})
        spec = create_spec(str(project_root), "done-002", "Done too", {"status": "READY"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)
        update_spec_status(spec.file_path, SpecStatus.DONE)

        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        assert all(p.pattern_type != "stuck" for p in patterns)


class TestFeedbackAnalysis:
    def test_analyzes_feedback_files(self, project_root: Path) -> None:
        spec = create_spec(str(project_root), "fb-001", "With feedback", {"status": "READY"})
        assert spec.file_path is not None

        feedback_dir = Path(spec.file_path).parent / "feedback"
        feedback_dir.mkdir(parents=True)
        (feedback_dir / "2026-01-01-001.md").write_text("Test failures found. Tests missing.", encoding="utf-8")
        (feedback_dir / "2026-01-02-002.md").write_text("Test coverage not met. Tests fail.", encoding="utf-8")

        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        feedback_patterns = [p for p in patterns if p.pattern_type.startswith("feedback_")]
        assert len(feedback_patterns) >= 1

    def test_no_feedback_no_patterns(self, project_root: Path) -> None:
        create_spec(str(project_root), "nofb-001", "No feedback", {"status": "READY"})
        analysis = RetrospectiveAnalysis(project_root)
        patterns = analysis.analyze_failure_patterns()
        feedback_patterns = [p for p in patterns if p.pattern_type.startswith("feedback_")]
        assert len(feedback_patterns) == 0


class TestMetrics:
    def test_empty_project(self, project_root: Path) -> None:
        analysis = RetrospectiveAnalysis(project_root)
        metrics = analysis.compute_metrics()
        assert metrics.total_specs == 0
        assert metrics.done_count == 0

    def test_counts_by_status(self, project_root: Path) -> None:
        create_spec(str(project_root), "m-001", "Ready", {"status": "READY"})
        spec2 = create_spec(str(project_root), "m-002", "Done", {"status": "READY"})
        assert spec2.file_path is not None
        update_spec_status(spec2.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec2.file_path, SpecStatus.REVIEW)
        update_spec_status(spec2.file_path, SpecStatus.DONE)

        analysis = RetrospectiveAnalysis(project_root)
        metrics = analysis.compute_metrics()
        assert metrics.total_specs == 2
        assert metrics.done_count == 1

    def test_cost_from_agent_logs(self, project_root: Path, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        agent_logger = AgentLogger(log_path)
        agent_logger.log(AgentLogEntry(agent="worker", model="sonnet", cost_usd=0.05, duration_ms=1000))
        agent_logger.log(AgentLogEntry(agent="quality_gate", model="sonnet", cost_usd=0.03, duration_ms=500))

        spec = create_spec(str(project_root), "cost-001", "Cost test", {"status": "READY"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)
        update_spec_status(spec.file_path, SpecStatus.DONE)

        analysis = RetrospectiveAnalysis(project_root, agent_log_path=str(log_path))
        metrics = analysis.compute_metrics()
        assert metrics.total_cost_usd == pytest.approx(0.08, abs=0.001)
        assert metrics.total_agent_calls == 2
        assert metrics.avg_duration_ms == 750.0
        assert metrics.cost_per_spec == pytest.approx(0.08, abs=0.001)

    def test_avg_retries(self, project_root: Path) -> None:
        create_spec(str(project_root), "r-001", "Task", {"status": "READY", "retries": 2})
        create_spec(str(project_root), "r-002", "Task", {"status": "READY", "retries": 4})

        analysis = RetrospectiveAnalysis(project_root)
        metrics = analysis.compute_metrics()
        assert metrics.avg_retries == 3.0


class TestAnalysisReport:
    def test_generates_report(self, project_root: Path) -> None:
        spec = create_spec(str(project_root), "rpt-001", "Stuck spec", {"status": "READY"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.STUCK)

        analysis = RetrospectiveAnalysis(project_root)
        report = analysis.generate_analysis_report()
        assert "# Retrospective Analysis" in report
        assert "## Metrics" in report
        assert "## Failure Patterns" in report
        assert "stuck" in report.lower()

    def test_empty_report(self, project_root: Path) -> None:
        analysis = RetrospectiveAnalysis(project_root)
        report = analysis.generate_analysis_report()
        assert "No failure patterns detected." in report
