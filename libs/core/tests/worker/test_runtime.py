"""Tests for Worker agent runtime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.fixtures.stub_plugin import StubWorker
from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.spec_io import create_spec, read_spec
from vizier.core.models.spec import SpecStatus
from vizier.core.worker.runtime import WorkerRuntime


def _make_llm_response(content: str = "done") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="test-model",
        _hidden_params={"response_cost": 0.001},
    )


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier" / "specs"
    vizier_dir.mkdir(parents=True)
    return str(tmp_path)


@pytest.fixture()
def ready_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "001-test-task",
        "Create output.txt with 'hello world'.",
        {"status": "READY", "priority": 1, "complexity": "low", "plugin": "test-stub"},
    )
    return spec.file_path or ""


@pytest.fixture()
def worker_context(project_dir: str, ready_spec: str) -> AgentContext:
    return AgentContext.load_from_disk(project_dir, spec_path=ready_spec)


@pytest.fixture()
def stub_worker() -> StubWorker:
    return StubWorker()


class TestWorkerRuntime:
    def test_role_is_worker(self, worker_context: AgentContext, stub_worker: StubWorker) -> None:
        runtime = WorkerRuntime(context=worker_context, plugin_worker=stub_worker)
        assert runtime.role == "worker"

    def test_build_prompt_uses_plugin_worker(self, worker_context: AgentContext, stub_worker: StubWorker) -> None:
        runtime = WorkerRuntime(context=worker_context, plugin_worker=stub_worker)
        prompt = runtime.build_prompt()
        assert "001-test-task" in prompt
        assert "output.txt" in prompt

    def test_build_prompt_requires_spec(self, stub_worker: StubWorker) -> None:
        ctx = AgentContext(project_root="/tmp/test")
        runtime = WorkerRuntime(context=ctx, plugin_worker=stub_worker)
        with pytest.raises(RuntimeError, match="requires a spec"):
            runtime.build_prompt()

    def test_process_response_transitions_to_review(
        self, worker_context: AgentContext, stub_worker: StubWorker, ready_spec: str
    ) -> None:
        WorkerRuntime.claim_spec(ready_spec, "worker-001")
        ctx = AgentContext.load_from_disk(worker_context.project_root, spec_path=ready_spec)
        runtime = WorkerRuntime(context=ctx, plugin_worker=stub_worker)
        response = _make_llm_response()
        result = runtime.process_response(response)

        assert result == "REVIEW"
        updated = read_spec(ready_spec)
        assert updated.frontmatter.status == SpecStatus.REVIEW

    def test_run_full_cycle(self, worker_context: AgentContext, stub_worker: StubWorker, ready_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response())
        WorkerRuntime.claim_spec(ready_spec, "worker-001")
        claimed = read_spec(ready_spec)
        assert claimed.frontmatter.status == SpecStatus.IN_PROGRESS
        assert claimed.frontmatter.assigned_to == "worker-001"

        ctx_in_progress = AgentContext.load_from_disk(worker_context.project_root, spec_path=ready_spec)
        runtime_ip = WorkerRuntime(
            context=ctx_in_progress,
            plugin_worker=stub_worker,
            llm_callable=mock_llm,
        )
        result = runtime_ip.run()

        assert result == "REVIEW"
        mock_llm.assert_called_once()
        final = read_spec(ready_spec)
        assert final.frontmatter.status == SpecStatus.REVIEW

    def test_exploration_logging(self, worker_context: AgentContext, stub_worker: StubWorker) -> None:
        runtime = WorkerRuntime(context=worker_context, plugin_worker=stub_worker)
        assert runtime.exploration_log == []

        runtime.log_exploration_read("/project/src/utils.py")
        runtime.log_exploration_read("/project/src/config.py")
        runtime.log_exploration_read("/project/src/utils.py")

        assert len(runtime.exploration_log) == 2
        assert "/project/src/utils.py" in runtime.exploration_log
        assert "/project/src/config.py" in runtime.exploration_log


class TestPickNextSpec:
    def test_picks_highest_priority(self, project_dir: str) -> None:
        create_spec(project_dir, "001-low-priority", "low", {"status": "READY", "priority": 3})
        create_spec(project_dir, "002-high-priority", "high", {"status": "READY", "priority": 1})
        create_spec(project_dir, "003-medium-priority", "medium", {"status": "READY", "priority": 2})

        picked = WorkerRuntime.pick_next_spec(project_dir)
        assert picked is not None
        spec = read_spec(picked)
        assert spec.frontmatter.id == "002-high-priority"

    def test_returns_none_when_no_ready(self, project_dir: str) -> None:
        create_spec(project_dir, "001-draft", "draft", {"status": "DRAFT"})
        picked = WorkerRuntime.pick_next_spec(project_dir)
        assert picked is None

    def test_returns_none_when_empty(self, project_dir: str) -> None:
        picked = WorkerRuntime.pick_next_spec(project_dir)
        assert picked is None


class TestClaimSpec:
    def test_transitions_to_in_progress(self, project_dir: str) -> None:
        spec = create_spec(project_dir, "001-claim-test", "test", {"status": "READY"})
        WorkerRuntime.claim_spec(spec.file_path or "", "worker-42")

        updated = read_spec(spec.file_path or "")
        assert updated.frontmatter.status == SpecStatus.IN_PROGRESS
        assert updated.frontmatter.assigned_to == "worker-42"

    def test_claim_non_ready_raises(self, project_dir: str) -> None:
        spec = create_spec(project_dir, "001-draft", "draft", {"status": "DRAFT"})
        with pytest.raises(ValueError, match="Invalid transition"):
            WorkerRuntime.claim_spec(spec.file_path or "", "worker-1")
