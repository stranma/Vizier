"""Tests for state manager with file locking."""

from __future__ import annotations

import json
import threading
from datetime import datetime

import pytest

from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.models.state import ActiveAgent, ProjectState


@pytest.fixture
def project_root(tmp_path):
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    return tmp_path


class TestStateManager:
    def test_read_nonexistent_returns_default(self, project_root) -> None:
        mgr = StateManager(project_root)
        state = mgr.read_state()
        assert state.project == project_root.name
        assert state.current_cycle == 0

    def test_write_and_read(self, project_root) -> None:
        mgr = StateManager(project_root)
        state = ProjectState(project="test-project", plugin="software", current_cycle=5)
        mgr.write_state(state)
        read_back = mgr.read_state()
        assert read_back.project == "test-project"
        assert read_back.current_cycle == 5

    def test_update_state_atomic(self, project_root) -> None:
        mgr = StateManager(project_root)
        mgr.write_state(ProjectState(project="test", current_cycle=0))

        result = mgr.update_state(lambda s: s.model_copy(update={"current_cycle": s.current_cycle + 1}))
        assert result.current_cycle == 1

        result = mgr.update_state(lambda s: s.model_copy(update={"current_cycle": s.current_cycle + 1}))
        assert result.current_cycle == 2

    def test_update_creates_file_if_missing(self, project_root) -> None:
        mgr = StateManager(project_root)
        result = mgr.update_state(lambda s: s.model_copy(update={"current_cycle": 42}))
        assert result.current_cycle == 42
        assert mgr.state_path.exists()

    def test_state_with_active_agents(self, project_root) -> None:
        mgr = StateManager(project_root)
        now = datetime(2026, 2, 15, 10, 0, 0)
        state = ProjectState(
            project="test",
            active_agents={"worker": ActiveAgent(pid=1234, since=now, spec="001-test")},
            queue=["002-next"],
        )
        mgr.write_state(state)
        read_back = mgr.read_state()
        assert "worker" in read_back.active_agents
        assert read_back.active_agents["worker"].pid == 1234
        assert read_back.queue == ["002-next"]

    def test_concurrent_updates(self, project_root) -> None:
        mgr = StateManager(project_root)
        mgr.write_state(ProjectState(project="test", current_cycle=0))

        errors: list[Exception] = []
        results: list[int] = []

        def increment() -> None:
            try:
                updated = mgr.update_state(lambda s: s.model_copy(update={"current_cycle": s.current_cycle + 1}))
                results.append(updated.current_cycle)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        final = mgr.read_state()
        assert final.current_cycle == 10

    def test_state_file_is_valid_json(self, project_root) -> None:
        mgr = StateManager(project_root)
        mgr.write_state(ProjectState(project="test"))
        data = json.loads(mgr.state_path.read_text(encoding="utf-8"))
        assert data["project"] == "test"
