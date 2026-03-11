"""Tests for RealmManager state management."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vizier_mcp.models.realm import ContainerStatus, Project, ProjectType
from vizier_mcp.realm import RealmManager

if TYPE_CHECKING:
    from pathlib import Path


class TestRealmManagerPersistence:
    def test_load_empty(self, realm: RealmManager) -> None:
        state = realm.load()
        assert state.projects == {}

    def test_save_and_load(self, realm: RealmManager) -> None:
        from vizier_mcp.models.realm import RealmState

        state = RealmState(projects={"test": Project(id="test")})
        realm.save(state)
        loaded = realm.load()
        assert "test" in loaded.projects
        assert loaded.projects["test"].id == "test"

    def test_realm_json_is_valid_json(self, realm: RealmManager) -> None:
        from vizier_mcp.models.realm import RealmState

        state = RealmState(projects={"a": Project(id="a")})
        realm.save(state)
        data = json.loads(realm.realm_path.read_text())
        assert "projects" in data
        assert "a" in data["projects"]

    def test_load_corrupted_file(self, realm: RealmManager) -> None:
        realm.realm_path.write_text("not json")
        state = realm.load()
        assert state.projects == {}


class TestRealmManagerCRUD:
    def test_add_project(self, realm: RealmManager) -> None:
        project = Project(id="my-proj")
        realm.add_project(project)
        loaded = realm.get_project("my-proj")
        assert loaded is not None
        assert loaded.id == "my-proj"

    def test_add_duplicate_raises(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="dup"))
        with pytest.raises(ValueError, match="already exists"):
            realm.add_project(Project(id="dup"))

    def test_get_nonexistent_returns_none(self, realm: RealmManager) -> None:
        assert realm.get_project("nope") is None

    def test_list_projects(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="a"))
        realm.add_project(Project(id="b", type=ProjectType.KNOWLEDGE))
        projects = realm.list_projects()
        assert len(projects) == 2

    def test_list_projects_with_filter(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="code", type=ProjectType.PROJECT))
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        projects = realm.list_projects("knowledge")
        assert len(projects) == 1
        assert projects[0]["id"] == "docs"

    def test_update_project(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="upd"))
        updated = realm.update_project("upd", status="archived")
        assert updated.status == "archived"
        reloaded = realm.get_project("upd")
        assert reloaded is not None
        assert reloaded.status == "archived"

    def test_update_nonexistent_raises(self, realm: RealmManager) -> None:
        with pytest.raises(KeyError, match="not found"):
            realm.update_project("ghost", status="x")


class TestRealmManagerContainerStatus:
    def test_update_container_status(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="proj"))
        realm.update_container_status("proj", ContainerStatus.RUNNING, "abc123")
        project = realm.get_project("proj")
        assert project is not None
        assert project.container_status == ContainerStatus.RUNNING
        assert project.container_name == "abc123"

    def test_update_container_status_nonexistent(self, realm: RealmManager) -> None:
        with pytest.raises(KeyError, match="not found"):
            realm.update_container_status("ghost", ContainerStatus.STOPPED)

    def test_repos_dir(self, tmp_vizier_root: Path) -> None:
        realm = RealmManager(tmp_vizier_root)
        assert realm.repos_dir == tmp_vizier_root / "repos"
