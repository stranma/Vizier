"""Tests for runtime state models."""

from datetime import datetime

from vizier.core.models.state import ActiveAgent, ProjectState


class TestActiveAgent:
    def test_creation(self) -> None:
        agent = ActiveAgent(pid=1234, since=datetime(2026, 2, 15, 10, 0, 0))
        assert agent.pid == 1234
        assert agent.spec is None

    def test_creation_with_spec(self) -> None:
        agent = ActiveAgent(pid=1234, since=datetime(2026, 2, 15, 10, 0, 0), spec="001-auth/002-jwt")
        assert agent.spec == "001-auth/002-jwt"


class TestProjectState:
    def test_minimal_creation(self) -> None:
        state = ProjectState(project="project-alpha")
        assert state.project == "project-alpha"
        assert state.plugin == "software"
        assert state.current_cycle == 0
        assert state.active_agents == {}
        assert state.queue == []
        assert state.last_retrospective is None

    def test_full_creation(self) -> None:
        now = datetime(2026, 2, 15, 10, 0, 0)
        state = ProjectState(
            project="project-alpha",
            plugin="documents",
            current_cycle=42,
            active_agents={
                "pasha": ActiveAgent(pid=1234, since=now),
                "worker": ActiveAgent(pid=1235, since=now, spec="001-auth/002-jwt"),
            },
            queue=["001-auth/003-login", "002-dashboard/001-layout"],
            last_retrospective=now,
        )
        assert state.current_cycle == 42
        assert len(state.active_agents) == 2
        assert state.active_agents["worker"].spec == "001-auth/002-jwt"
        assert len(state.queue) == 2

    def test_serialization_roundtrip(self) -> None:
        now = datetime(2026, 2, 15, 10, 0, 0)
        state = ProjectState(
            project="test",
            active_agents={"worker": ActiveAgent(pid=100, since=now)},
            queue=["spec-1"],
        )
        data = state.model_dump()
        restored = ProjectState.model_validate(data)
        assert restored == state
