"""Tests for container lifecycle tools."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from vizier_mcp.models.realm import ContainerStatus, Project, ProjectType
from vizier_mcp.tools.container import container_start, container_status, container_stop

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager


def _setup_project(realm: RealmManager, project_id: str = "test-proj", with_devcontainer: bool = True) -> None:
    """Add a project and create its repo directory."""
    realm.add_project(Project(id=project_id))
    repo_dir = realm.repos_dir / project_id
    repo_dir.mkdir(parents=True, exist_ok=True)
    if with_devcontainer:
        (repo_dir / ".devcontainer").mkdir()
        (repo_dir / ".devcontainer" / "devcontainer.json").write_text("{}")


class TestContainerStart:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await container_start(realm, "ghost")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.anyio
    async def test_knowledge_project_rejected(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        result = await container_start(realm, "docs")
        assert "error" in result
        assert "Knowledge" in result["error"]

    @pytest.mark.anyio
    async def test_missing_devcontainer(self, realm: RealmManager) -> None:
        _setup_project(realm, "no-dc", with_devcontainer=False)
        result = await container_start(realm, "no-dc")
        assert "error" in result
        assert ".devcontainer" in result["error"]

    @pytest.mark.anyio
    async def test_successful_start(self, realm: RealmManager) -> None:
        _setup_project(realm)
        mock_result = '{"containerId": "abc123def456"}'
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(0, mock_result, "")),
        ):
            result = await container_start(realm, "test-proj")
        assert result["status"] == "running"
        assert result["container_name"] == "abc123def456"
        project = realm.get_project("test-proj")
        assert project is not None
        assert project.container_status == ContainerStatus.RUNNING

    @pytest.mark.anyio
    async def test_failed_start(self, realm: RealmManager) -> None:
        _setup_project(realm)
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(1, "", "build failed")),
        ):
            result = await container_start(realm, "test-proj")
        assert "error" in result
        project = realm.get_project("test-proj")
        assert project is not None
        assert project.container_status == ContainerStatus.ERROR

    @pytest.mark.anyio
    async def test_start_without_container_id(self, realm: RealmManager) -> None:
        _setup_project(realm)
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(0, "not json", "")),
        ):
            result = await container_start(realm, "test-proj")
        assert result["status"] == "running"
        assert result["container_name"] == "vizier-test-proj"


class TestContainerStop:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await container_stop(realm, "ghost")
        assert "error" in result

    @pytest.mark.anyio
    async def test_already_stopped(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="stopped"))
        result = await container_stop(realm, "stopped")
        assert result["status"] == "already_stopped"

    @pytest.mark.anyio
    async def test_stop_running_container(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="running", container_name="abc123", container_status=ContainerStatus.RUNNING))
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(0, "abc123", "")),
        ):
            result = await container_stop(realm, "running")
        assert result["status"] == "stopped"
        project = realm.get_project("running")
        assert project is not None
        assert project.container_status == ContainerStatus.STOPPED

    @pytest.mark.anyio
    async def test_stop_already_removed_container(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="removed", container_name="gone", container_status=ContainerStatus.RUNNING))
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(1, "", "No such container")),
        ):
            result = await container_stop(realm, "removed")
        assert result["status"] == "stopped"

    @pytest.mark.anyio
    async def test_no_container_name(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="noname", container_status=ContainerStatus.RUNNING))
        result = await container_stop(realm, "noname")
        assert result["status"] == "stopped"


class TestContainerStatus:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await container_status(realm, "ghost")
        assert "error" in result

    @pytest.mark.anyio
    async def test_no_container(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="nocontainer"))
        result = await container_status(realm, "nocontainer")
        assert result["docker_status"] == "no_container"

    @pytest.mark.anyio
    async def test_running_container(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="running", container_name="abc", container_status=ContainerStatus.RUNNING))
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(0, "running\n", "")),
        ):
            result = await container_status(realm, "running")
        assert result["docker_status"] == "running"
        assert result["realm_status"] == "running"

    @pytest.mark.anyio
    async def test_reconciles_stale_state(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="stale", container_name="abc", container_status=ContainerStatus.RUNNING))
        with patch(
            "vizier_mcp.tools.container._run_subprocess",
            new=AsyncMock(return_value=(1, "", "No such container")),
        ):
            result = await container_status(realm, "stale")
        assert result["docker_status"] == "not_found"
        assert result["realm_status"] == "stopped"
        assert result["reconciled"] is True
