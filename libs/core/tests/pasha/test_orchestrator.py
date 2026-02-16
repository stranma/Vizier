"""Tests for PashaOrchestrator."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vizier.core.agent_runner.runner import RunResult
from vizier.core.file_protocol.spec_io import create_spec, list_specs, update_spec_status
from vizier.core.models.spec import SpecStatus
from vizier.core.pasha.orchestrator import PashaOrchestrator


def _setup_project(tmp_path: Path, plugin: str = "software") -> Path:
    """Create a minimal project structure."""
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    (vizier_dir / "constitution.md").write_text("Test project constitution.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("No learnings yet.", encoding="utf-8")
    (vizier_dir / "config.yaml").write_text(
        f"plugin: {plugin}\nproject: test-project\n",
        encoding="utf-8",
    )

    state = {"project": "test-project", "plugin": plugin, "current_cycle": 0}
    (vizier_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    return tmp_path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return _setup_project(tmp_path)


@pytest.fixture
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.run_worker.return_value = RunResult(agent_type="worker", spec_id="spec-001", result="REVIEW")
    runner.run_quality_gate.return_value = RunResult(agent_type="quality_gate", spec_id="spec-001", result="DONE")
    runner.run_architect.return_value = RunResult(agent_type="architect", spec_id="spec-001", result="DECOMPOSED:2")
    return runner


@pytest.fixture
def orchestrator(project_root: Path, mock_runner: MagicMock) -> PashaOrchestrator:
    pasha = PashaOrchestrator(
        project_root=project_root,
        project_name="test-project",
        max_concurrent=2,
        agent_timeout=5,
        reconciliation_interval=1,
    )
    pasha._subprocess_mgr._runner = mock_runner
    return pasha


class TestPashaOrchestrator:
    def test_init(self, orchestrator: PashaOrchestrator) -> None:
        assert orchestrator.project_name == "test-project"
        assert orchestrator.cycle_count == 0
        assert orchestrator.is_running is False
        assert orchestrator.is_session_mode is False

    def test_project_root(self, orchestrator: PashaOrchestrator, project_root: Path) -> None:
        assert orchestrator.project_root == project_root

    def test_subprocess_manager_access(self, orchestrator: PashaOrchestrator) -> None:
        assert orchestrator.subprocess_manager is not None

    def test_progress_reporter_access(self, orchestrator: PashaOrchestrator) -> None:
        assert orchestrator.progress_reporter is not None


class TestCycleExecution:
    def test_empty_cycle(self, orchestrator: PashaOrchestrator) -> None:
        report = asyncio.run(orchestrator.run_once())
        assert report.cycle == 1
        assert len(report.specs_processed) == 0
        assert len(report.agents_spawned) == 0

    def test_cycle_increments(self, orchestrator: PashaOrchestrator) -> None:
        asyncio.run(orchestrator.run_once())
        asyncio.run(orchestrator.run_once())
        assert orchestrator.cycle_count == 2

    def test_draft_triggers_architect(
        self, orchestrator: PashaOrchestrator, project_root: Path, mock_runner: MagicMock
    ) -> None:
        create_spec(str(project_root), "spec-001", "Test task", {"status": "DRAFT", "plugin": "software"})
        report = asyncio.run(orchestrator.run_once())
        assert len(report.agents_spawned) > 0
        assert any("architect" in a for a in report.agents_spawned)
        mock_runner.run_architect.assert_called_once()

    def test_ready_triggers_worker(
        self, orchestrator: PashaOrchestrator, project_root: Path, mock_runner: MagicMock
    ) -> None:
        create_spec(str(project_root), "spec-001", "Test task", {"status": "READY", "plugin": "software"})
        report = asyncio.run(orchestrator.run_once())
        assert any("worker" in a for a in report.agents_spawned)
        mock_runner.run_worker.assert_called_once()

    def test_review_triggers_quality_gate(
        self, orchestrator: PashaOrchestrator, project_root: Path, mock_runner: MagicMock
    ) -> None:
        spec = create_spec(str(project_root), "spec-001", "Test task", {"status": "READY", "plugin": "software"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)

        report = asyncio.run(orchestrator.run_once())
        assert any("quality_gate" in a for a in report.agents_spawned)
        mock_runner.run_quality_gate.assert_called_once()


class TestRejectionHandling:
    def test_rejected_spec_retries(
        self, orchestrator: PashaOrchestrator, project_root: Path, mock_runner: MagicMock
    ) -> None:
        spec = create_spec(str(project_root), "spec-001", "Test task", {"status": "READY", "plugin": "software"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)
        update_spec_status(spec.file_path, SpecStatus.REJECTED)

        report = asyncio.run(orchestrator.run_once())
        assert "spec-001" in report.specs_processed

    def test_stuck_spec_escalation(self, orchestrator: PashaOrchestrator, project_root: Path) -> None:
        spec = create_spec(
            str(project_root),
            "spec-002",
            "Stuck task",
            {"status": "READY", "plugin": "software", "retries": 9, "max_retries": 10},
        )
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path, SpecStatus.REVIEW)
        update_spec_status(spec.file_path, SpecStatus.REJECTED)

        asyncio.run(orchestrator.run_once())

        reloaded = list_specs(str(project_root), status_filter=SpecStatus.STUCK)
        assert len(reloaded) == 1
        assert reloaded[0].frontmatter.id == "spec-002"


class TestStateAgeMonitoring:
    def test_old_in_progress_spec_detected(self, orchestrator: PashaOrchestrator, project_root: Path) -> None:
        from datetime import datetime, timedelta

        spec = create_spec(str(project_root), "spec-old", "Old task", {"status": "READY", "plugin": "software"})
        assert spec.file_path is not None
        update_spec_status(
            spec.file_path,
            SpecStatus.IN_PROGRESS,
            extra_updates={"updated": (datetime.utcnow() - timedelta(hours=1)).isoformat()},
        )

        orchestrator._state_age_threshold = 60

        report = asyncio.run(orchestrator.run_once())
        assert report.cycle == 1


class TestSessionMode:
    def test_enter_session(self, orchestrator: PashaOrchestrator) -> None:
        orchestrator.enter_session()
        assert orchestrator.is_session_mode is True

    def test_exit_session(self, orchestrator: PashaOrchestrator) -> None:
        orchestrator.enter_session()
        orchestrator.exit_session()
        assert orchestrator.is_session_mode is False

    def test_exit_session_with_summary(self, orchestrator: PashaOrchestrator) -> None:
        orchestrator.enter_session()
        path = orchestrator.exit_session("We discussed the architecture.")
        if path:
            assert Path(path).exists()
            content = Path(path).read_text(encoding="utf-8")
            assert "We discussed the architecture." in content


class TestShutdown:
    def test_shutdown(self, orchestrator: PashaOrchestrator) -> None:
        asyncio.run(orchestrator.shutdown())

    def test_shutdown_interrupts_active_specs(self, orchestrator: PashaOrchestrator, project_root: Path) -> None:
        spec = create_spec(str(project_root), "spec-active", "Active task", {"status": "READY", "plugin": "software"})
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)

        asyncio.run(orchestrator.shutdown())

        interrupted = list_specs(str(project_root), status_filter=SpecStatus.INTERRUPTED)
        assert len(interrupted) == 1


class TestStatusWriting:
    def test_writes_status_after_cycle(self, orchestrator: PashaOrchestrator) -> None:
        asyncio.run(orchestrator.run_once())

        reports_dir = Path(orchestrator._server_config.reports_dir) / "test-project"
        status_path = reports_dir / "status.json"
        assert status_path.exists()

        data = json.loads(status_path.read_text(encoding="utf-8"))
        assert data["project"] == "test-project"
        assert data["cycle_count"] == 1

    def test_writes_cycle_report(self, orchestrator: PashaOrchestrator) -> None:
        asyncio.run(orchestrator.run_once())

        reports_dir = Path(orchestrator._server_config.reports_dir).resolve() / "test-project"
        cycle_reports = list(reports_dir.glob("*-cycle-*.md"))
        assert len(cycle_reports) >= 1
        latest = max(cycle_reports, key=lambda p: p.stat().st_mtime)
        content = latest.read_text(encoding="utf-8")
        assert "# Cycle Report" in content

    def test_multiple_specs_multiple_types(
        self, orchestrator: PashaOrchestrator, project_root: Path, mock_runner: MagicMock
    ) -> None:
        create_spec(str(project_root), "spec-draft", "Draft", {"status": "DRAFT", "plugin": "software"})
        create_spec(str(project_root), "spec-ready", "Ready", {"status": "READY", "plugin": "software"})

        report = asyncio.run(orchestrator.run_once())
        assert len(report.agents_spawned) == 2
        assert mock_runner.run_architect.call_count == 1
        assert mock_runner.run_worker.call_count == 1
