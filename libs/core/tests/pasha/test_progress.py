"""Tests for Pasha progress reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vizier.core.pasha.progress import CycleReport, ProgressReporter, ProjectStatus


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    return tmp_path / "reports" / "test-project"


@pytest.fixture
def reporter(reports_dir: Path) -> ProgressReporter:
    return ProgressReporter(reports_dir)


class TestProjectStatus:
    def test_default_values(self) -> None:
        status = ProjectStatus()
        assert status.project == ""
        assert status.total_specs == 0
        assert status.by_status == {}
        assert status.active_agents == 0
        assert status.cycle_count == 0

    def test_with_values(self) -> None:
        status = ProjectStatus(
            project="alpha",
            timestamp="2026-01-01T00:00:00",
            total_specs=5,
            by_status={"READY": 2, "DONE": 3},
            active_agents=1,
            cycle_count=10,
        )
        assert status.project == "alpha"
        assert status.total_specs == 5
        assert status.by_status["READY"] == 2


class TestCycleReport:
    def test_default_values(self) -> None:
        report = CycleReport()
        assert report.cycle == 0
        assert report.specs_processed == []
        assert report.agents_spawned == []
        assert report.errors == []

    def test_with_values(self) -> None:
        report = CycleReport(
            cycle=5,
            timestamp="2026-01-01T00:00:00",
            specs_processed=["spec-001", "spec-002"],
            agents_spawned=["worker:spec-001"],
            errors=["timeout on spec-002"],
        )
        assert report.cycle == 5
        assert len(report.specs_processed) == 2


class TestProgressReporter:
    def test_write_status(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        status = ProjectStatus(
            project="alpha",
            timestamp="2026-01-01T00:00:00",
            total_specs=3,
            by_status={"READY": 1, "DONE": 2},
        )
        path = reporter.write_status(status)
        assert Path(path).exists()

        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["project"] == "alpha"
        assert data["total_specs"] == 3
        assert data["by_status"]["READY"] == 1

    def test_write_status_creates_dir(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        assert not reports_dir.exists()
        reporter.write_status(ProjectStatus(project="test"))
        assert reports_dir.exists()

    def test_write_status_overwrites(self, reporter: ProgressReporter) -> None:
        reporter.write_status(ProjectStatus(project="v1", total_specs=1))
        path = reporter.write_status(ProjectStatus(project="v2", total_specs=5))
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        assert data["project"] == "v2"
        assert data["total_specs"] == 5

    def test_write_cycle_report(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        report = CycleReport(
            cycle=1,
            timestamp="2026-01-01T00:00:00",
            specs_processed=["spec-001"],
            agents_spawned=["worker:spec-001"],
        )
        path = reporter.write_cycle_report(report)
        assert Path(path).exists()

        content = Path(path).read_text(encoding="utf-8")
        assert "# Cycle Report 1" in content
        assert "spec-001" in content
        assert "worker:spec-001" in content

    def test_write_cycle_report_empty_lists(self, reporter: ProgressReporter) -> None:
        report = CycleReport(cycle=2, timestamp="2026-01-01T00:00:00")
        path = reporter.write_cycle_report(report)
        content = Path(path).read_text(encoding="utf-8")
        assert "(none)" in content

    def test_write_cycle_report_with_errors(self, reporter: ProgressReporter) -> None:
        report = CycleReport(
            cycle=3,
            timestamp="2026-01-01T00:00:00",
            errors=["Agent timed out", "Plugin not found"],
        )
        path = reporter.write_cycle_report(report)
        content = Path(path).read_text(encoding="utf-8")
        assert "## Errors" in content
        assert "Agent timed out" in content

    def test_write_escalation(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        path = reporter.write_escalation("spec-001", "STUCK after retries", "Exhausted 10 retries")
        assert Path(path).exists()

        content = Path(path).read_text(encoding="utf-8")
        assert "# Escalation: spec-001" in content
        assert "STUCK after retries" in content
        assert "Exhausted 10 retries" in content

    def test_write_escalation_creates_subdir(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        assert not (reports_dir / "escalations").exists()
        reporter.write_escalation("spec-001", "test")
        assert (reports_dir / "escalations").exists()

    def test_write_escalation_no_details(self, reporter: ProgressReporter) -> None:
        path = reporter.write_escalation("spec-002", "test reason")
        content = Path(path).read_text(encoding="utf-8")
        assert "No additional details." in content

    def test_no_tmp_files_left(self, reporter: ProgressReporter, reports_dir: Path) -> None:
        reporter.write_status(ProjectStatus(project="test"))
        reporter.write_cycle_report(CycleReport(cycle=1, timestamp="now"))
        reporter.write_escalation("spec-001", "test")

        tmp_files = list(reports_dir.rglob("*.tmp"))
        assert len(tmp_files) == 0
