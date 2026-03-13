"""Tests for realm models."""

from __future__ import annotations

from vizier_mcp.models.realm import (
    ContainerStatus,
    PashaManifest,
    PashaState,
    PashaStatus,
    Project,
    ProjectType,
    RealmState,
)


class TestProject:
    def test_default_values(self) -> None:
        p = Project(id="test-project")
        assert p.type == ProjectType.PROJECT
        assert p.container_status == ContainerStatus.STOPPED
        assert p.git_url is None
        assert p.template == "stranma/claude-code-python-template"
        assert p.knowledge_links == []

    def test_knowledge_project(self) -> None:
        p = Project(id="docs", type=ProjectType.KNOWLEDGE)
        assert p.type == ProjectType.KNOWLEDGE

    def test_default_pasha_state(self) -> None:
        p = Project(id="test-project")
        assert p.pasha.status == PashaStatus.IDLE
        assert p.pasha.task is None
        assert p.pasha.pid is None

    def test_to_summary(self) -> None:
        p = Project(id="my-proj", git_url="https://github.com/x/y.git")
        summary = p.to_summary()
        assert summary["id"] == "my-proj"
        assert summary["type"] == "project"
        assert summary["git_url"] == "https://github.com/x/y.git"
        assert summary["container_status"] == "stopped"
        assert summary["pasha_status"] == "idle"
        assert summary["pasha_task"] is None

    def test_serialization_roundtrip(self) -> None:
        p = Project(id="test", git_url="https://example.com/repo.git", knowledge_links=["docs"])
        data = p.model_dump(mode="json")
        p2 = Project.model_validate(data)
        assert p2.id == p.id
        assert p2.git_url == p.git_url
        assert p2.knowledge_links == ["docs"]


class TestPashaManifest:
    def test_default_values(self) -> None:
        m = PashaManifest(name="test-pasha")
        assert m.version == "1.0.0"
        assert m.runtime == "openclaw"
        assert m.entrypoint == ".pasha/launch.sh"
        assert m.status_file == ".pasha/status.json"
        assert m.capabilities == []
        assert m.env_requires == []

    def test_full_manifest(self) -> None:
        m = PashaManifest(
            name="custom",
            version="2.0.0",
            runtime="docker",
            entrypoint="/start.sh",
            capabilities=["git", "docker"],
            env_requires=["API_KEY"],
        )
        assert m.name == "custom"
        assert m.capabilities == ["git", "docker"]

    def test_serialization_roundtrip(self) -> None:
        m = PashaManifest(name="rt", capabilities=["net"])
        data = m.model_dump(mode="json")
        m2 = PashaManifest.model_validate(data)
        assert m2.name == m.name
        assert m2.capabilities == ["net"]


class TestPashaState:
    def test_default_values(self) -> None:
        s = PashaState()
        assert s.status == PashaStatus.IDLE
        assert s.task is None
        assert s.cost_spent == 0.0
        assert s.pid is None

    def test_running_state(self) -> None:
        s = PashaState(
            status=PashaStatus.RUNNING,
            task="build feature",
            acceptance_criteria=["tests pass"],
            cost_limit=5.0,
            pid=123,
        )
        assert s.status == PashaStatus.RUNNING
        assert s.acceptance_criteria == ["tests pass"]

    def test_serialization_roundtrip(self) -> None:
        s = PashaState(status=PashaStatus.COMPLETED, task="done", cost_spent=2.5)
        data = s.model_dump(mode="json")
        s2 = PashaState.model_validate(data)
        assert s2.status == PashaStatus.COMPLETED
        assert s2.cost_spent == 2.5


class TestRealmState:
    def test_empty_state(self) -> None:
        state = RealmState()
        assert state.projects == {}

    def test_state_with_projects(self) -> None:
        state = RealmState(projects={"a": Project(id="a"), "b": Project(id="b")})
        assert len(state.projects) == 2
        assert "a" in state.projects

    def test_serialization_roundtrip(self) -> None:
        state = RealmState(projects={"x": Project(id="x", type=ProjectType.KNOWLEDGE)})
        data = state.model_dump(mode="json")
        state2 = RealmState.model_validate(data)
        assert state2.projects["x"].type == ProjectType.KNOWLEDGE
