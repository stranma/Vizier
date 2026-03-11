"""Tests for realm models."""

from __future__ import annotations

from vizier_mcp.models.realm import ContainerStatus, Project, ProjectType, RealmState


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

    def test_to_summary(self) -> None:
        p = Project(id="my-proj", git_url="https://github.com/x/y.git")
        summary = p.to_summary()
        assert summary["id"] == "my-proj"
        assert summary["type"] == "project"
        assert summary["git_url"] == "https://github.com/x/y.git"
        assert summary["container_status"] == "stopped"

    def test_serialization_roundtrip(self) -> None:
        p = Project(id="test", git_url="https://example.com/repo.git", knowledge_links=["docs"])
        data = p.model_dump(mode="json")
        p2 = Project.model_validate(data)
        assert p2.id == p.id
        assert p2.git_url == p.git_url
        assert p2.knowledge_links == ["docs"]


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
