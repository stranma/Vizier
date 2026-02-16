"""Integration test: full inner loop (Worker -> QualityGate -> DONE/REJECTED)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tests.fixtures.stub_plugin import StubPlugin, StubQualityGate, StubWorker
from vizier.core.agent.context import AgentContext
from vizier.core.agent_runner.runner import AgentRunner
from vizier.core.file_protocol.spec_io import create_spec, read_spec, update_spec_status
from vizier.core.lifecycle.retry import GraduatedRetry, RetryAction
from vizier.core.lifecycle.spec_lifecycle import SpecLifecycle
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.discovery import clear_registry, register_plugin
from vizier.core.quality_gate.runtime import QualityGateRuntime
from vizier.core.worker.runtime import WorkerRuntime


def _make_llm_response(content: str = "done") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="test-model",
        _hidden_params={"response_cost": 0.001},
    )


@pytest.fixture(autouse=True)
def _register_stub() -> Any:
    register_plugin("test-stub", StubPlugin)
    yield
    clear_registry()


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    specs_dir = vizier_dir / "specs"
    specs_dir.mkdir()
    config_path = vizier_dir / "config.yaml"
    config_path.write_text(yaml.dump({"plugin": "test-stub", "project": "test-project"}), encoding="utf-8")
    return str(tmp_path)


class TestFullInnerLoop:
    """End-to-end: READY -> Worker -> REVIEW -> QualityGate -> DONE."""

    def test_happy_path_to_done(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-happy",
            "Create output.txt",
            {"status": "READY", "priority": 1, "plugin": "test-stub"},
        )
        spec_path = spec.file_path or ""

        mock_llm = MagicMock(return_value=_make_llm_response("Implementation complete."))
        worker = StubWorker()
        WorkerRuntime.claim_spec(spec_path, "w-001")

        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        worker_runtime = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        worker_result = worker_runtime.run()
        assert worker_result == "REVIEW"

        gate = StubQualityGate()
        ctx2 = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        gate_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        gate_runtime = QualityGateRuntime(
            context=ctx2,
            plugin_gate=gate,
            diff="+ valid code",
            llm_callable=gate_llm,
        )
        gate_result = gate_runtime.run_full_protocol()
        assert gate_result == "DONE"

        final = read_spec(spec_path)
        assert final.frontmatter.status == SpecStatus.DONE

    def test_rejection_and_retry(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-retry",
            "Create output.txt",
            {"status": "READY", "priority": 1, "plugin": "test-stub"},
        )
        spec_path = spec.file_path or ""

        mock_llm = MagicMock(return_value=_make_llm_response())
        worker = StubWorker()
        WorkerRuntime.claim_spec(spec_path, "w-001")
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        w_runtime = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        w_runtime.run()

        gate = StubQualityGate()
        ctx2 = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        gate_runtime = QualityGateRuntime(
            context=ctx2,
            plugin_gate=gate,
            diff="+ print('debug')",
        )
        gate_result = gate_runtime.run_full_protocol()
        assert gate_result == "REJECTED"

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.CONTINUE

        spec_after = read_spec(spec_path)
        assert spec_after.frontmatter.status == SpecStatus.IN_PROGRESS
        assert spec_after.frontmatter.retries == 1

    def test_stuck_after_max_retries(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-stuck",
            "Impossible task",
            {"status": "READY", "priority": 1, "plugin": "test-stub"},
        )
        spec_path = spec.file_path or ""

        update_spec_status(spec_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec_path, SpecStatus.REVIEW)
        update_spec_status(spec_path, SpecStatus.REJECTED, extra_updates={"retries": 9})

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.STUCK

        final = read_spec(spec_path)
        assert final.frontmatter.status == SpecStatus.STUCK

    def test_interrupted_and_requeued(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-interrupt",
            "In-progress task",
            {"status": "READY", "priority": 1, "plugin": "test-stub"},
        )
        update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS, {"assigned_to": "w-001"})

        interrupted = SpecLifecycle.interrupt_active_specs(project_dir)
        assert "001-interrupt" in interrupted

        s = read_spec(spec.file_path or "")
        assert s.frontmatter.status == SpecStatus.INTERRUPTED

        requeued = SpecLifecycle.handle_interrupted_specs(project_dir)
        assert "001-interrupt" in requeued

        s2 = read_spec(spec.file_path or "")
        assert s2.frontmatter.status == SpecStatus.READY

    def test_agent_runner_full_cycle(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-runner",
            "Agent runner test",
            {"status": "READY", "priority": 1, "plugin": "test-stub"},
        )

        mock_llm = MagicMock(return_value=_make_llm_response("Implementation done."))
        runner = AgentRunner(project_root=project_dir, llm_callable=mock_llm)

        worker_result = runner.run_worker(spec.file_path or "", worker_id="w-001")
        assert worker_result.result == "REVIEW"

        gate_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        gate_runner = AgentRunner(project_root=project_dir, llm_callable=gate_llm)
        gate_result = gate_runner.run_quality_gate(spec.file_path or "", diff="+ valid code")
        assert gate_result.result == "DONE"


class TestGraduatedRetryIntegration:
    def test_model_bump_at_retry_3(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-bump",
            "Task requiring model bump",
            {"status": "READY", "plugin": "test-stub"},
        )
        spec_path = spec.file_path or ""

        update_spec_status(spec_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec_path, SpecStatus.REVIEW)
        update_spec_status(spec_path, SpecStatus.REJECTED, extra_updates={"retries": 2})

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.BUMP_MODEL

        retry = GraduatedRetry()
        new_tier = retry.get_bumped_tier("haiku")
        assert new_tier == "sonnet"

    def test_repeated_action_escalation(self) -> None:
        retry = GraduatedRetry()
        actions = ["read_file /src/main.py", "read_file /src/main.py", "read_file /src/main.py"]
        assert retry.check_repeated_actions(actions) is True

    def test_fresh_context_per_worker(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "001-fresh",
            "Fresh context test",
            {"status": "READY", "plugin": "test-stub"},
        )
        mock_llm = MagicMock(return_value=_make_llm_response())
        worker = StubWorker()

        WorkerRuntime.claim_spec(spec.file_path or "", "w-001")
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec.file_path)

        runtime = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        runtime.log_exploration_read("/extra/file.py")

        runtime2 = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        assert runtime2.exploration_log == []
