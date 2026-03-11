"""Container lifecycle tools for Vizier v2.

Provides MCP tools to start, stop, and check status of project
devcontainers using the devcontainer CLI and Docker.

Security note: All subprocess calls use create_subprocess_exec (not shell)
to prevent command injection. Arguments are passed as separate list elements.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.realm import ContainerStatus

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager

logger = logging.getLogger(__name__)


async def _run_subprocess(cmd: list[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a subprocess safely and return (returncode, stdout, stderr).

    Uses create_subprocess_exec (no shell) to prevent injection.
    All arguments are passed as separate list elements.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return -1, "", "Command timed out"

    return proc.returncode or 0, stdout_bytes.decode(), stderr_bytes.decode()


async def container_start(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Build and start a project's devcontainer.

    Uses ``devcontainer up`` to create/start the container.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Dict with container status or error.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    if project.type.value == "knowledge":
        return {"error": "Knowledge projects don't have containers"}

    repo_dir = realm.repos_dir / project_id
    if not repo_dir.exists():
        return {"error": f"Repository directory not found: {repo_dir}"}

    devcontainer_dir = repo_dir / ".devcontainer"
    if not devcontainer_dir.exists():
        return {"error": f"No .devcontainer/ found in {repo_dir}. Create project with a template first."}

    realm.update_container_status(project_id, ContainerStatus.STARTING)

    returncode, stdout, stderr = await _run_subprocess(
        ["devcontainer", "up", "--workspace-folder", str(repo_dir)],
        timeout=600,
    )

    if returncode != 0:
        realm.update_container_status(project_id, ContainerStatus.ERROR)
        return {
            "error": f"devcontainer up failed (exit {returncode})",
            "stderr": stderr.strip(),
            "stdout": stdout.strip(),
        }

    container_name = None
    try:
        result = json.loads(stdout)
        container_name = result.get("containerId", "")[:12] if result.get("containerId") else None
    except (json.JSONDecodeError, KeyError):
        pass

    if not container_name:
        container_name = f"vizier-{project_id}"

    realm.update_container_status(project_id, ContainerStatus.RUNNING, container_name)

    return {
        "project_id": project_id,
        "container_name": container_name,
        "status": "running",
    }


async def container_stop(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Stop a project's devcontainer.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Dict with status or error.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    if project.container_status == ContainerStatus.STOPPED:
        return {"project_id": project_id, "status": "already_stopped"}

    container_name = project.container_name
    if not container_name:
        realm.update_container_status(project_id, ContainerStatus.STOPPED)
        return {"project_id": project_id, "status": "stopped", "detail": "No container name recorded"}

    returncode, stdout, stderr = await _run_subprocess(
        ["docker", "stop", container_name],
        timeout=30,
    )

    if returncode != 0:
        if "No such container" in stderr or "No such container" in stdout:
            realm.update_container_status(project_id, ContainerStatus.STOPPED, container_name=None)
            return {"project_id": project_id, "status": "stopped", "detail": "Container already removed"}
        return {
            "error": f"docker stop failed (exit {returncode})",
            "stderr": stderr.strip(),
        }

    realm.update_container_status(project_id, ContainerStatus.STOPPED)
    return {"project_id": project_id, "status": "stopped"}


async def container_status(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Check container state for a project.

    Queries Docker for actual container state and reconciles with realm.json.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Dict with container status details.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    result: dict[str, Any] = {
        "project_id": project_id,
        "realm_status": project.container_status.value,
        "container_name": project.container_name,
    }

    if not project.container_name:
        result["docker_status"] = "no_container"
        return result

    returncode, stdout, _stderr = await _run_subprocess(
        ["docker", "inspect", "--format", "{{.State.Status}}", project.container_name],
        timeout=10,
    )

    if returncode != 0:
        result["docker_status"] = "not_found"
        if project.container_status != ContainerStatus.STOPPED:
            realm.update_container_status(project_id, ContainerStatus.STOPPED)
            result["realm_status"] = "stopped"
            result["reconciled"] = True
    else:
        docker_state = stdout.strip()
        result["docker_status"] = docker_state

        expected = ContainerStatus.RUNNING if docker_state == "running" else ContainerStatus.STOPPED
        if project.container_status != expected:
            realm.update_container_status(project_id, expected)
            result["realm_status"] = expected.value
            result["reconciled"] = True

    return result
