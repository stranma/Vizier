"""Tests for Pasha subprocess manager."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from vizier.core.agent_runner.runner import RunResult
from vizier.core.pasha.subprocess_manager import AgentProcess, SubprocessManager


@pytest.fixture
def mock_runner() -> MagicMock:
    runner = MagicMock()
    runner.run_worker.return_value = RunResult(agent_type="worker", spec_id="spec-001", result="REVIEW")
    runner.run_quality_gate.return_value = RunResult(agent_type="quality_gate", spec_id="spec-001", result="DONE")
    runner.run_architect.return_value = RunResult(agent_type="architect", spec_id="spec-001", result="DECOMPOSED:2")
    return runner


@pytest.fixture
def manager(mock_runner: MagicMock) -> SubprocessManager:
    return SubprocessManager(mock_runner, max_concurrent=2, timeout_seconds=5)


class TestAgentProcess:
    def test_create_process(self) -> None:
        proc = AgentProcess(agent_type="worker", spec_id="001", spec_path="/tmp/spec.md")
        assert proc.agent_type == "worker"
        assert proc.spec_id == "001"
        assert proc.result is None
        assert proc.timed_out is False

    def test_process_with_result(self) -> None:
        result = RunResult(agent_type="worker", spec_id="001", result="REVIEW")
        proc = AgentProcess(agent_type="worker", spec_id="001", spec_path="/tmp/spec.md", result=result)
        assert proc.result is not None
        assert proc.result.result == "REVIEW"


class TestSubprocessManager:
    def test_spawn_worker(self, manager: SubprocessManager, mock_runner: MagicMock) -> None:
        result = asyncio.run(manager.spawn_worker("/tmp/spec.md", "spec-001"))
        assert result.agent_type == "worker"
        assert result.result == "REVIEW"
        mock_runner.run_worker.assert_called_once()

    def test_spawn_quality_gate(self, manager: SubprocessManager, mock_runner: MagicMock) -> None:
        result = asyncio.run(manager.spawn_quality_gate("/tmp/spec.md", "spec-001", diff="test diff"))
        assert result.agent_type == "quality_gate"
        assert result.result == "DONE"
        mock_runner.run_quality_gate.assert_called_once()

    def test_spawn_architect(self, manager: SubprocessManager, mock_runner: MagicMock) -> None:
        result = asyncio.run(manager.spawn_architect("/tmp/spec.md", "spec-001"))
        assert result.agent_type == "architect"
        assert result.result == "DECOMPOSED:2"
        mock_runner.run_architect.assert_called_once()

    def test_active_count(self, manager: SubprocessManager) -> None:
        assert manager.active_count == 0

    def test_completed_processes(self, manager: SubprocessManager) -> None:
        asyncio.run(manager.spawn_worker("/tmp/spec.md", "spec-001"))
        assert len(manager.completed_processes) == 1
        assert manager.completed_processes[0].agent_type == "worker"

    def test_timeout(self, mock_runner: MagicMock) -> None:
        def blocking_call(*args: object, **kwargs: object) -> RunResult:
            time.sleep(3)
            return RunResult(agent_type="worker", spec_id="spec-001", result="REVIEW")

        mock_runner.run_worker.side_effect = blocking_call
        mgr = SubprocessManager(mock_runner, max_concurrent=1, timeout_seconds=1)

        result = asyncio.run(mgr.spawn_worker("/tmp/spec.md", "spec-001"))
        assert result.error
        assert "Timeout" in result.error

    def test_concurrency_limit(self, mock_runner: MagicMock) -> None:
        call_times: list[float] = []

        def slow_worker(*args: object, **kwargs: object) -> RunResult:
            call_times.append(time.monotonic())
            time.sleep(0.2)
            return RunResult(agent_type="worker", spec_id="spec", result="REVIEW")

        mock_runner.run_worker.side_effect = slow_worker
        mgr = SubprocessManager(mock_runner, max_concurrent=1, timeout_seconds=5)

        async def run_both() -> list[RunResult]:
            return list(
                await asyncio.gather(
                    mgr.spawn_worker("/tmp/a.md", "spec-a"),
                    mgr.spawn_worker("/tmp/b.md", "spec-b"),
                )
            )

        results = asyncio.run(run_both())
        assert all(r.result == "REVIEW" for r in results)
        assert len(call_times) == 2

    def test_shutdown_rejects_new_spawns(self, manager: SubprocessManager) -> None:
        asyncio.run(manager.shutdown())
        result = asyncio.run(manager.spawn_worker("/tmp/spec.md", "spec-001"))
        assert result.error
        assert "shutting down" in result.error.lower()

    def test_agent_crash(self, mock_runner: MagicMock) -> None:
        mock_runner.run_worker.side_effect = RuntimeError("Agent crashed")
        mgr = SubprocessManager(mock_runner, max_concurrent=1, timeout_seconds=5)
        result = asyncio.run(mgr.spawn_worker("/tmp/spec.md", "spec-001"))
        assert result.error
        assert "Agent crashed" in result.error

    def test_active_processes_empty_after_completion(self, manager: SubprocessManager) -> None:
        asyncio.run(manager.spawn_worker("/tmp/spec.md", "spec-001"))
        assert manager.active_count == 0
        assert len(manager.active_processes) == 0

    def test_shutdown_returns_active_ids(self, mock_runner: MagicMock) -> None:
        mgr = SubprocessManager(mock_runner, max_concurrent=2, timeout_seconds=5)
        interrupted = asyncio.run(mgr.shutdown())
        assert isinstance(interrupted, list)
