"""Golden path integration tests: end-to-end agent handoffs with mocked LLM.

These tests validate the full lifecycle using mocked Anthropic responses.
Real LLM validation is done manually per Phase 22 plan.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.ea.factory import create_ea_runtime
from vizier.core.agents.pasha.event_loop import PashaEventLoop
from vizier.core.agents.quality_gate.factory import create_quality_gate_runtime
from vizier.core.agents.scout.factory import create_scout_runtime
from vizier.core.agents.worker.factory import create_worker_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response, make_tool_use_response


class TestHappyPath:
    """End-to-end: EA -> Pasha -> Scout -> Worker -> QG -> DONE."""

    def test_ea_creates_spec_seed(self) -> None:
        client = make_mock_client(
            make_tool_use_response("create_spec", {"spec_id": "001", "goal": "Add auth"}),
            make_text_response("Spec created and delegated."),
        )
        runtime = create_ea_runtime(client=client, initial_message="Build auth")
        result = runtime.run("Build authentication for project-alpha")
        assert result.stop_reason == StopReason.COMPLETED

    def test_scout_researches_and_completes(self) -> None:
        client = make_mock_client(
            make_tool_use_response("read_file", {"path": ".vizier/specs/001/spec.md"}),
            make_tool_use_response(
                "send_message",
                {"type": "RESEARCH_REPORT", "spec_id": "001", "confidence": 0.9},
            ),
            make_tool_use_response("update_spec_status", {"spec_id": "001", "status": "SCOUTED"}),
            make_text_response("Research complete."),
        )
        runtime = create_scout_runtime(client=client, spec_id="001")
        result = runtime.run("Research spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_worker_executes_and_transitions_to_review(self) -> None:
        client = make_mock_client(
            make_tool_use_response("read_file", {"path": "src/auth.py"}),
            make_tool_use_response("write_file", {"path": "src/auth.py", "content": "def login(): pass"}),
            make_tool_use_response("run_tests", {"command": "pytest tests/"}),
            make_tool_use_response("git", {"command": "commit -m 'Add auth'"}),
            make_tool_use_response("update_spec_status", {"spec_id": "001", "status": "REVIEW"}),
            make_text_response("Work complete."),
        )
        runtime = create_worker_runtime(
            client=client,
            spec_id="001",
            goal="Add authentication",
        )
        result = runtime.run("Execute spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_quality_gate_approves(self) -> None:
        client = make_mock_client(
            make_tool_use_response("run_tests", {"command": "pytest"}),
            make_tool_use_response("bash", {"command": "ruff check ."}),
            make_tool_use_response("read_file", {"path": "src/auth.py"}),
            make_tool_use_response("update_spec_status", {"spec_id": "001", "status": "DONE"}),
            make_text_response("All criteria pass. Verdict: PASS"),
        )
        runtime = create_quality_gate_runtime(
            client=client,
            spec_id="001",
            acceptance_criteria="All tests pass",
        )
        result = runtime.run("Validate spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_pasha_event_loop_detects_ready_specs(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "READY")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))

        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert "002" in result["ready_for_assignment"]
        assert result["completed_specs"] == 1


class TestEscalationPath:
    """Worker stuck -> graduated retry -> STUCK -> Retrospective."""

    def test_worker_escalates_to_pasha(self) -> None:
        client = make_mock_client(
            make_tool_use_response("read_file", {"path": "src/complex.py"}),
            make_tool_use_response(
                "ping_supervisor",
                {"spec_id": "001", "urgency": "BLOCKER", "message": "Cannot proceed"},
            ),
            make_text_response("Escalated to supervisor."),
        )
        runtime = create_worker_runtime(
            client=client,
            spec_id="001",
            goal="Complex refactoring",
        )
        result = runtime.run("Execute spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_pasha_processes_blocker_ping(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        ping_dir = spec_dir / "pings"
        ping_dir.mkdir(parents=True)
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))
        (ping_dir / "ping-001.json").write_text(json.dumps({"urgency": "BLOCKER", "message": "Cannot proceed"}))

        loop = PashaEventLoop(project_root=str(tmp_path))
        pings = loop.scan_pings()
        actions = loop.process_pings(pings)
        assert len(actions) == 1
        assert actions[0]["action"] == "escalate_to_ea"

    def test_graduated_retry_model_bump(self) -> None:
        from vizier.core.agents.pasha.retry import RetryAction, make_retry_decision

        decision = make_retry_decision(3, "sonnet")
        assert decision.action == RetryAction.MODEL_BUMP
        assert decision.model_tier == "opus"

    def test_graduated_retry_stuck(self) -> None:
        from vizier.core.agents.pasha.retry import RetryAction, make_retry_decision

        decision = make_retry_decision(10, "opus")
        assert decision.action == RetryAction.STUCK


class TestRejectionLoop:
    """QG rejects -> Worker retries with feedback -> QG approves."""

    def test_quality_gate_rejects(self) -> None:
        client = make_mock_client(
            make_tool_use_response("run_tests", {"command": "pytest"}),
            make_tool_use_response(
                "write_feedback",
                {"spec_id": "001", "feedback": "Missing edge case tests"},
            ),
            make_tool_use_response("update_spec_status", {"spec_id": "001", "status": "REJECTED"}),
            make_text_response("Verdict: FAIL. Missing tests."),
        )
        runtime = create_quality_gate_runtime(
            client=client,
            spec_id="001",
            acceptance_criteria="All edge cases tested",
        )
        result = runtime.run("Validate spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_worker_retries_after_rejection(self) -> None:
        client = make_mock_client(
            make_tool_use_response("read_file", {"path": ".vizier/specs/001/feedback/latest.md"}),
            make_tool_use_response("write_file", {"path": "tests/test_edge.py", "content": "def test_edge(): ..."}),
            make_tool_use_response("run_tests", {"command": "pytest tests/test_edge.py"}),
            make_tool_use_response("update_spec_status", {"spec_id": "001", "status": "REVIEW"}),
            make_text_response("Edge cases added."),
        )
        runtime = create_worker_runtime(
            client=client,
            spec_id="001",
            goal="Fix edge case coverage",
            retry_count=1,
        )
        result = runtime.run("Retry spec 001 with feedback")
        assert result.stop_reason == StopReason.COMPLETED


class TestDAGScheduling:
    """Architect creates DAG, Pasha schedules respecting dependencies."""

    def test_pasha_holds_blocked_spec(self, tmp_path: Path) -> None:
        for sid in ["001", "002"]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)

        (tmp_path / ".vizier" / "specs" / "001" / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))
        (tmp_path / ".vizier" / "specs" / "002" / "state.json").write_text(
            json.dumps({"status": "READY", "depends_on": ["001"]})
        )

        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert result["ready_for_assignment"] == []

    def test_pasha_releases_after_dependency_done(self, tmp_path: Path) -> None:
        for sid in ["001", "002"]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)

        (tmp_path / ".vizier" / "specs" / "001" / "state.json").write_text(json.dumps({"status": "DONE"}))
        (tmp_path / ".vizier" / "specs" / "002" / "state.json").write_text(
            json.dumps({"status": "READY", "depends_on": ["001"]})
        )

        loop = PashaEventLoop(project_root=str(tmp_path))
        result = loop.run_reconciliation_cycle()
        assert "002" in result["ready_for_assignment"]

    def test_dag_validates_no_cycles(self) -> None:
        from vizier.core.scheduling.dag_validator import DagNode

        loop = PashaEventLoop(project_root="/tmp")
        nodes = [
            DagNode(spec_id="001", depends_on=["002"]),
            DagNode(spec_id="002", depends_on=["001"]),
        ]
        valid, msg = loop.check_dag_validity(nodes)
        assert valid is False
        assert "cycle" in str(msg).lower()


class TestGracefulShutdown:
    """System recovers from agent crashes."""

    def test_shutdown_and_recover(self, tmp_path: Path) -> None:
        from vizier.core.agents.pasha.shutdown import graceful_shutdown, recover_interrupted

        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "IN_PROGRESS"}))

        interrupted = graceful_shutdown(str(tmp_path))
        assert interrupted == ["001"]

        recovered = recover_interrupted(str(tmp_path))
        assert recovered == ["001"]


class TestBudgetEnforcement:
    """Budget tracking across agent runtime."""

    def test_runtime_tracks_budget(self) -> None:
        client = make_mock_client(
            make_text_response("Done", input_tokens=1000, output_tokens=500),
        )
        runtime = create_worker_runtime(client=client, spec_id="001", goal="Small task")
        result = runtime.run("Do work")
        assert result.tokens_used > 0
        assert runtime.budget.tokens_remaining < 100000


class TestEvidenceCompleteness:
    """QG evidence validation."""

    def test_complete_evidence(self, tmp_path: Path) -> None:
        evidence_dir = tmp_path / ".vizier" / "specs" / "001" / "evidence"
        evidence_dir.mkdir(parents=True)
        for ev in ["test_output", "lint_output", "type_check_output", "diff"]:
            (evidence_dir / f"{ev}.txt").write_text("evidence data")

        loop = PashaEventLoop(project_root=str(tmp_path), plugin_name="software")
        complete, _missing = loop.check_evidence_completeness("001")
        assert complete is True

    def test_incomplete_evidence(self, tmp_path: Path) -> None:
        evidence_dir = tmp_path / ".vizier" / "specs" / "001" / "evidence"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "test_output.txt").write_text("tests passed")

        loop = PashaEventLoop(project_root=str(tmp_path), plugin_name="software")
        complete, missing = loop.check_evidence_completeness("001")
        assert complete is False
        assert "lint_output" in missing
