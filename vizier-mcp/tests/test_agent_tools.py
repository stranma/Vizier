"""Tests for agent control tools (pasha_launch, pasha_status, agent_kill, knowledge_link)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from vizier_mcp.models.realm import ContainerStatus, PashaStatus, Project, ProjectType
from vizier_mcp.tools.agent import agent_kill, knowledge_link, pasha_launch, pasha_status

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager

MOCK_MANIFEST = json.dumps(
    {
        "name": "test-pasha",
        "version": "1.0.0",
        "runtime": "hermes",
        "entrypoint": ".pasha/launch.sh",
        "status_file": ".pasha/status.json",
    }
)


def _add_running_project(realm: RealmManager, project_id: str = "proj") -> None:
    """Add a project with a running container."""
    realm.add_project(
        Project(
            id=project_id,
            container_name="abc123",
            container_status=ContainerStatus.RUNNING,
        )
    )


class TestPashaLaunch:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await pasha_launch(realm, "ghost", "do stuff")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.anyio
    async def test_knowledge_project_rejected(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        result = await pasha_launch(realm, "docs", "do stuff")
        assert "error" in result
        assert "knowledge" in result["error"].lower()

    @pytest.mark.anyio
    async def test_container_not_running(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="stopped"))
        result = await pasha_launch(realm, "stopped", "do stuff")
        assert "error" in result
        assert "not running" in result["error"].lower()

    @pytest.mark.anyio
    async def test_pasha_already_running(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="existing task")
        result = await pasha_launch(realm, "proj", "new task")
        assert "error" in result
        assert "already running" in result["error"].lower()

    @pytest.mark.anyio
    async def test_no_manifest(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        with patch(
            "vizier_mcp.tools.agent._run_subprocess",
            new=AsyncMock(return_value=(1, "", "No such file")),
        ):
            result = await pasha_launch(realm, "proj", "do stuff")
        assert "error" in result
        assert "manifest" in result["error"].lower()

    @pytest.mark.anyio
    async def test_invalid_manifest(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        with patch(
            "vizier_mcp.tools.agent._run_subprocess",
            new=AsyncMock(return_value=(0, "not json", "")),
        ):
            result = await pasha_launch(realm, "proj", "do stuff")
        assert "error" in result
        assert "invalid manifest" in result["error"].lower()

    @pytest.mark.anyio
    async def test_manifest_missing_required_field(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        # Manifest without required 'name' field
        with patch(
            "vizier_mcp.tools.agent._run_subprocess",
            new=AsyncMock(return_value=(0, '{"version": "1.0.0"}', "")),
        ):
            result = await pasha_launch(realm, "proj", "do stuff")
        assert "error" in result

    @pytest.mark.anyio
    async def test_successful_launch(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        call_count = 0

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            nonlocal call_count
            call_count += 1
            if "cat" in cmd and "manifest.json" in cmd[-1]:
                return (0, MOCK_MANIFEST, "")
            if "tee" in cmd:
                return (0, "", "")
            if "-d" in cmd:
                return (0, "", "")
            if "pgrep" in cmd:
                return (0, "42\n", "")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await pasha_launch(realm, "proj", "build feature", ["tests pass"], 10.0)

        assert result["pasha_status"] == "running"
        assert result["manifest_name"] == "test-pasha"
        assert result["task"] == "build feature"
        assert result["pid"] == 42

        project = realm.get_project("proj")
        assert project is not None
        assert project.pasha.status == PashaStatus.RUNNING
        assert project.pasha.task == "build feature"
        assert project.pasha.acceptance_criteria == ["tests pass"]
        assert project.pasha.cost_limit == 10.0
        assert project.pasha.pid == 42

    @pytest.mark.anyio
    async def test_docker_exec_failure(self, realm: RealmManager) -> None:
        _add_running_project(realm)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "cat" in cmd and "manifest.json" in cmd[-1]:
                return (0, MOCK_MANIFEST, "")
            if "tee" in cmd:
                return (1, "", "write failed")
            # Fallback write also fails
            if "sh" in cmd:
                return (1, "", "write failed")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await pasha_launch(realm, "proj", "do stuff")
        assert "error" in result
        assert "task.json" in result["error"].lower()


class TestPashaStatus:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await pasha_status(realm, "ghost")
        assert "error" in result

    @pytest.mark.anyio
    async def test_idle_no_docker_call(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        # No mock needed -- idle Pasha should not make docker calls
        result = await pasha_status(realm, "proj")
        assert result["pasha_status"] == "idle"
        assert result["task"] is None

    @pytest.mark.anyio
    async def test_running_and_alive(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="work", pid=42)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "kill" in cmd and "-0" in cmd:
                return (0, "", "")
            if "cat" in cmd and "status.json" in cmd[-1]:
                return (1, "", "No such file")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await pasha_status(realm, "proj")

        assert result["pasha_status"] == "running"
        assert result["process_alive"] is True

    @pytest.mark.anyio
    async def test_running_alive_with_status_file(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="work", pid=42)
        status_content = json.dumps({"state": "in_progress", "progress": 50})

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "kill" in cmd and "-0" in cmd:
                return (0, "", "")
            if "cat" in cmd and "status.json" in cmd[-1]:
                return (0, status_content, "")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await pasha_status(realm, "proj")

        assert result["pasha_status"] == "running"
        assert result["status_file"]["state"] == "in_progress"

    @pytest.mark.anyio
    async def test_running_dead_reconciles(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="work", pid=42)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "kill" in cmd and "-0" in cmd:
                return (1, "", "No such process")
            if "cat" in cmd:
                return (1, "", "No such file")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await pasha_status(realm, "proj")

        assert result["pasha_status"] == "completed"
        assert result["reconciled"] is True
        project = realm.get_project("proj")
        assert project is not None
        assert project.pasha.status == PashaStatus.COMPLETED

    @pytest.mark.anyio
    async def test_already_completed(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.COMPLETED, task="done")
        result = await pasha_status(realm, "proj")
        assert result["pasha_status"] == "completed"


class TestAgentKill:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await agent_kill(realm, "ghost")
        assert "error" in result

    @pytest.mark.anyio
    async def test_container_not_running(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="stopped"))
        result = await agent_kill(realm, "stopped")
        assert "error" in result
        assert "not running" in result["error"].lower()

    @pytest.mark.anyio
    async def test_no_agents_idempotent(self, realm: RealmManager) -> None:
        _add_running_project(realm)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            # pkill finds nothing -- returns 1
            return (1, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await agent_kill(realm, "proj")

        assert result["pasha_status"] == "killed"
        project = realm.get_project("proj")
        assert project is not None
        assert project.pasha.status == PashaStatus.KILLED

    @pytest.mark.anyio
    async def test_kill_by_pid(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="work", pid=42)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "kill" in cmd and "42" in cmd:
                return (0, "", "")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await agent_kill(realm, "proj")

        assert result["pasha_status"] == "killed"
        assert result["killed_pid"] == 42

    @pytest.mark.anyio
    async def test_kill_pid_already_dead(self, realm: RealmManager) -> None:
        _add_running_project(realm)
        realm.update_pasha_state("proj", status=PashaStatus.RUNNING, task="work", pid=99)

        async def mock_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
            if "kill" in cmd and "99" in cmd:
                return (1, "", "No such process")
            if "pkill" in cmd:
                return (1, "", "")
            return (0, "", "")

        with patch("vizier_mcp.tools.agent._run_subprocess", new=AsyncMock(side_effect=mock_subprocess)):
            result = await agent_kill(realm, "proj")

        assert result["pasha_status"] == "killed"
        assert result["killed_pid"] is None


class TestKnowledgeLink:
    @pytest.mark.anyio
    async def test_project_not_found(self, realm: RealmManager) -> None:
        result = await knowledge_link(realm, "ghost", "docs")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.anyio
    async def test_knowledge_not_found(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="proj"))
        result = await knowledge_link(realm, "proj", "ghost-docs")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.anyio
    async def test_wrong_target_type(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        realm.add_project(Project(id="other-docs", type=ProjectType.KNOWLEDGE))
        result = await knowledge_link(realm, "docs", "other-docs")
        assert "error" in result
        assert "must be a project" in result["error"].lower()

    @pytest.mark.anyio
    async def test_wrong_source_type(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="proj1"))
        realm.add_project(Project(id="proj2"))
        result = await knowledge_link(realm, "proj1", "proj2")
        assert "error" in result
        assert "must be a knowledge" in result["error"].lower()

    @pytest.mark.anyio
    async def test_successful_link(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="proj"))
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        result = await knowledge_link(realm, "proj", "docs")
        assert result["linked"] is True
        assert result["total_links"] == 1

        project = realm.get_project("proj")
        assert project is not None
        assert "docs" in project.knowledge_links

    @pytest.mark.anyio
    async def test_duplicate_link(self, realm: RealmManager) -> None:
        realm.add_project(Project(id="proj", knowledge_links=["docs"]))
        realm.add_project(Project(id="docs", type=ProjectType.KNOWLEDGE))
        result = await knowledge_link(realm, "proj", "docs")
        assert result["linked"] is True
        assert result["detail"] == "already linked"
