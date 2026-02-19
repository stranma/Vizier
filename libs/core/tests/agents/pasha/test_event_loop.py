"""Tests for Pasha event loop: spec scanning, ping handling, reconciliation."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.pasha.event_loop import PashaEventLoop, PingEvent
from vizier.core.scheduling.dag_validator import DagNode


class TestScanPings:
    def test_no_pings(self, tmp_path: Path) -> None:
        (tmp_path / ".vizier" / "specs" / "001").mkdir(parents=True)
        loop = PashaEventLoop(project_root=str(tmp_path))
        assert loop.scan_pings() == []

    def test_finds_pings(self, tmp_path: Path) -> None:
        ping_dir = tmp_path / ".vizier" / "specs" / "001" / "pings"
        ping_dir.mkdir(parents=True)
        ping = {"urgency": "QUESTION", "message": "Need clarification"}
        (ping_dir / "ping-001.json").write_text(json.dumps(ping))
        loop = PashaEventLoop(project_root=str(tmp_path))
        pings = loop.scan_pings()
        assert len(pings) == 1
        assert pings[0].urgency == "QUESTION"
        assert pings[0].spec_id == "001"

    def test_skips_invalid_json(self, tmp_path: Path) -> None:
        ping_dir = tmp_path / ".vizier" / "specs" / "001" / "pings"
        ping_dir.mkdir(parents=True)
        (ping_dir / "bad.json").write_text("{invalid")
        loop = PashaEventLoop(project_root=str(tmp_path))
        assert loop.scan_pings() == []

    def test_nonexistent_dir(self) -> None:
        loop = PashaEventLoop(project_root="/nonexistent")
        assert loop.scan_pings() == []


class TestProcessPings:
    def test_blocker_escalates(self) -> None:
        loop = PashaEventLoop(project_root="/tmp")
        pings = [PingEvent(spec_id="001", urgency="BLOCKER", message="Cannot proceed", file_path="")]
        actions = loop.process_pings(pings)
        assert len(actions) == 1
        assert actions[0]["action"] == "escalate_to_ea"
        assert actions[0]["immediate"] is True

    def test_question_immediate(self) -> None:
        loop = PashaEventLoop(project_root="/tmp")
        pings = [PingEvent(spec_id="001", urgency="QUESTION", message="Which API?", file_path="")]
        actions = loop.process_pings(pings)
        assert actions[0]["action"] == "process_immediately"
        assert actions[0]["immediate"] is True

    def test_info_deferred(self) -> None:
        loop = PashaEventLoop(project_root="/tmp")
        pings = [PingEvent(spec_id="001", urgency="INFO", message="FYI update", file_path="")]
        actions = loop.process_pings(pings)
        assert actions[0]["action"] == "note_for_report"
        assert actions[0]["immediate"] is False


class TestScanSpecs:
    def test_no_specs(self, tmp_path: Path) -> None:
        loop = PashaEventLoop(project_root=str(tmp_path))
        assert loop.scan_specs() == []

    def test_finds_specs(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001-auth"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        specs = loop.scan_specs()
        assert len(specs) == 1
        assert specs[0].spec_id == "001-auth"
        assert specs[0].status == "IN_PROGRESS"

    def test_multiple_specs(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "IN_PROGRESS"), ("003", "READY")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        specs = loop.scan_specs()
        assert len(specs) == 3


class TestDAGValidation:
    def test_valid_dag(self) -> None:
        loop = PashaEventLoop(project_root="/tmp")
        nodes = [DagNode(spec_id="001"), DagNode(spec_id="002", depends_on=["001"])]
        valid, result = loop.check_dag_validity(nodes)
        assert valid is True
        assert result == ["001", "002"]

    def test_invalid_dag_cycle(self) -> None:
        loop = PashaEventLoop(project_root="/tmp")
        nodes = [
            DagNode(spec_id="001", depends_on=["002"]),
            DagNode(spec_id="002", depends_on=["001"]),
        ]
        valid, result = loop.check_dag_validity(nodes)
        assert valid is False
        assert "cycle" in str(result).lower()


class TestEvidenceCompleteness:
    def test_complete_evidence(self, tmp_path: Path) -> None:
        evidence_dir = tmp_path / ".vizier" / "specs" / "001" / "evidence"
        evidence_dir.mkdir(parents=True)
        for ev in ["test_output", "lint_output", "type_check_output", "diff"]:
            (evidence_dir / f"{ev}.txt").write_text("evidence")
        loop = PashaEventLoop(project_root=str(tmp_path), plugin_name="software")
        complete, missing = loop.check_evidence_completeness("001")
        assert complete is True
        assert missing == []

    def test_missing_evidence(self, tmp_path: Path) -> None:
        evidence_dir = tmp_path / ".vizier" / "specs" / "001" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "test_output.txt").write_text("PASSED")
        loop = PashaEventLoop(project_root=str(tmp_path), plugin_name="software")
        complete, missing = loop.check_evidence_completeness("001")
        assert complete is False
        assert "lint_output" in missing


class TestSpecsReadyForAssignment:
    def test_ready_no_deps(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "READY"}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        from vizier.core.agents.pasha.event_loop import SpecEvent

        specs = [SpecEvent(spec_id="001", status="READY", event_type="check")]
        ready = loop.specs_ready_for_assignment(specs, set())
        assert ready == ["001"]

    def test_blocked_by_dependency(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "002"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "READY", "depends_on": ["001"]}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        from vizier.core.agents.pasha.event_loop import SpecEvent

        specs = [SpecEvent(spec_id="002", status="READY", event_type="check")]
        ready = loop.specs_ready_for_assignment(specs, set())
        assert ready == []

    def test_unblocked_by_completed_dep(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "002"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "READY", "depends_on": ["001"]}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        from vizier.core.agents.pasha.event_loop import SpecEvent

        specs = [SpecEvent(spec_id="002", status="READY", event_type="check")]
        ready = loop.specs_ready_for_assignment(specs, {"001"})
        assert ready == ["002"]


class TestReconciliationCycle:
    def test_empty_project(self, tmp_path: Path) -> None:
        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert result["cycle"] == 1
        assert result["total_specs"] == 0

    def test_cycle_increments(self, tmp_path: Path) -> None:
        loop = PashaEventLoop(project_root=str(tmp_path))
        loop.run_reconciliation_cycle()
        loop.run_reconciliation_cycle()
        assert loop.state.cycle_count == 2

    def test_tracks_active_specs(self, tmp_path: Path) -> None:
        for sid, status in [("001", "IN_PROGRESS"), ("002", "DONE"), ("003", "REVIEW")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert result["active_specs"] == 2
        assert result["completed_specs"] == 1

    def test_finds_ready_specs(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "READY")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))
        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert "002" in result["ready_for_assignment"]
