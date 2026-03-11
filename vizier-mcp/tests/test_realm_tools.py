"""Tests for realm management tools."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from vizier_mcp.models.realm import Project, ProjectType
from vizier_mcp.tools.realm import (
    _validate_project_id,
    realm_create_project,
    realm_get_project,
    realm_list_projects,
)

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager


class TestValidateProjectId:
    def test_valid_ids(self) -> None:
        assert _validate_project_id("my-project") is None
        assert _validate_project_id("a") is None
        assert _validate_project_id("test123") is None
        assert _validate_project_id("a-b-c") is None

    def test_empty(self) -> None:
        assert _validate_project_id("") is not None

    def test_too_long(self) -> None:
        assert _validate_project_id("a" * 64) is not None

    def test_invalid_chars(self) -> None:
        assert _validate_project_id("My_Project") is not None
        assert _validate_project_id("test project") is not None
        assert _validate_project_id("-starts-with-dash") is not None


class TestRealmListProjects:
    def test_empty_realm(self, realm: RealmManager) -> None:
        result = realm_list_projects(realm)
        assert result["count"] == 0
        assert result["projects"] == []

    def test_with_projects(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="a"))
        realm.add_project(Project(id="b", type=ProjectType.KNOWLEDGE))
        result = realm_list_projects(realm)
        assert result["count"] == 2

    def test_filter_by_type(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="code"))
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        result = realm_list_projects(realm, type_filter="knowledge")
        assert result["count"] == 1
        assert result["projects"][0]["id"] == "docs"


class TestRealmCreateProject:
    @pytest.mark.anyio
    async def test_create_scaffold(self, realm: RealmManager) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=True)):
            result = await realm_create_project(realm, "test-proj")
        assert "error" not in result
        assert result["project_id"] == "test-proj"
        assert result["type"] == "project"
        assert result["devcontainer"] is True

    @pytest.mark.anyio
    async def test_create_knowledge_project(self, realm: RealmManager) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=True)):
            result = await realm_create_project(realm, "my-docs", project_type="knowledge")
        assert result["type"] == "knowledge"

    @pytest.mark.anyio
    async def test_invalid_project_id(self, realm: RealmManager) -> None:
        result = await realm_create_project(realm, "Invalid ID!")
        assert "error" in result

    @pytest.mark.anyio
    async def test_invalid_project_type(self, realm: RealmManager) -> None:
        result = await realm_create_project(realm, "test", project_type="invalid")
        assert "error" in result

    @pytest.mark.anyio
    async def test_duplicate_project(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="dup"))
        result = await realm_create_project(realm, "dup")
        assert "error" in result
        assert "already exists" in result["error"]

    @pytest.mark.anyio
    async def test_project_saved_in_realm(self, realm: RealmManager) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=False)):
            await realm_create_project(realm, "saved")
        project = realm.get_project("saved")
        assert project is not None
        assert project.id == "saved"

    @pytest.mark.anyio
    async def test_repo_dir_created(self, realm: RealmManager) -> None:
        with patch("vizier_mcp.tools.realm._fetch_devcontainer", new=AsyncMock(return_value=False)):
            await realm_create_project(realm, "repo-test")
        repo_dir = realm.repos_dir / "repo-test"
        assert repo_dir.exists()
        assert (repo_dir / ".git").exists()


class TestRealmGetProject:
    def test_existing_project(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="get-test", git_url="https://github.com/x/y.git"))
        result = realm_get_project(realm, "get-test")
        assert result["id"] == "get-test"
        assert result["git_url"] == "https://github.com/x/y.git"

    def test_nonexistent_project(self, realm: RealmManager) -> None:
        result = realm_get_project(realm, "ghost")
        assert "error" in result
        assert "not found" in result["error"]
