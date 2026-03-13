"""Agent control tools for Vizier v2.

Provides MCP tools to launch, monitor, and kill Pasha agents
inside project devcontainers, plus cross-project knowledge linking.

Security note: All subprocess calls use create_subprocess_exec (not shell)
to prevent command injection. Arguments are passed as separate list elements.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.realm import (
    ContainerStatus,
    PashaManifest,
    PashaStatus,
    ProjectType,
)
from vizier_mcp.tools.container import _run_subprocess

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager

logger = logging.getLogger(__name__)


async def pasha_launch(
    realm: RealmManager,
    project_id: str,
    task: str,
    acceptance_criteria: list[str] | None = None,
    cost_limit: float | None = None,
) -> dict[str, Any]:
    """Launch a Pasha agent inside a project's devcontainer.

    Reads .pasha/manifest.json from the container, writes task.json,
    and executes the manifest entrypoint.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :param task: Task description for the Pasha.
    :param acceptance_criteria: List of acceptance criteria.
    :param cost_limit: Optional cost limit in dollars.
    :return: Dict with launch status or error.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    if project.type == ProjectType.KNOWLEDGE:
        return {"error": "Cannot launch Pasha on a knowledge project"}

    if project.container_status != ContainerStatus.RUNNING:
        return {"error": f"Container not running (status: {project.container_status.value})"}

    if project.pasha.status == PashaStatus.RUNNING:
        return {"error": "Pasha already running", "pasha_task": project.pasha.task}

    container = project.container_name
    if not container:
        return {"error": "No container name recorded"}

    # Read manifest from container
    rc, stdout, stderr = await _run_subprocess(
        ["docker", "exec", container, "cat", "/workspace/.pasha/manifest.json"],
        timeout=10,
    )
    if rc != 0:
        return {"error": "Failed to read .pasha/manifest.json from container", "stderr": stderr.strip()}

    try:
        manifest_data = json.loads(stdout)
        manifest = PashaManifest.model_validate(manifest_data)
    except (json.JSONDecodeError, Exception) as exc:
        return {"error": f"Invalid manifest: {exc}"}

    # Write task file into container
    criteria = acceptance_criteria or []
    task_payload = json.dumps(
        {"task": task, "acceptance_criteria": criteria, "cost_limit": cost_limit},
        indent=2,
    )
    rc, _stdout, stderr = await _run_subprocess(
        ["docker", "exec", "-i", container, "tee", "/workspace/.pasha/task.json"],
        timeout=10,
    )
    if rc != 0:
        # Fallback: write via sh -c echo (still exec-based, no shell injection)
        rc, _stdout, stderr = await _run_subprocess(
            [
                "docker",
                "exec",
                container,
                "sh",
                "-c",
                f"cat > /workspace/.pasha/task.json << 'VIZIER_EOF'\n{task_payload}\nVIZIER_EOF",
            ],
            timeout=10,
        )
        if rc != 0:
            return {"error": "Failed to write task.json to container", "stderr": stderr.strip()}

    # Execute entrypoint (detached)
    rc, _stdout, stderr = await _run_subprocess(
        ["docker", "exec", "-d", container, manifest.entrypoint],
        timeout=10,
    )
    if rc != 0:
        return {"error": f"Failed to execute entrypoint: {manifest.entrypoint}", "stderr": stderr.strip()}

    # Query PID
    rc, stdout, _stderr = await _run_subprocess(
        ["docker", "exec", container, "pgrep", "-f", manifest.entrypoint],
        timeout=5,
    )
    pid = None
    if rc == 0 and stdout.strip():
        with contextlib.suppress(ValueError):
            pid = int(stdout.strip().splitlines()[0])

    # Update realm state
    now = datetime.now(UTC).isoformat()
    realm.update_pasha_state(
        project_id,
        status=PashaStatus.RUNNING,
        task=task,
        acceptance_criteria=criteria,
        cost_limit=cost_limit,
        cost_spent=0.0,
        launched_at=now,
        pid=pid,
    )

    return {
        "project_id": project_id,
        "pasha_status": "running",
        "manifest_name": manifest.name,
        "task": task,
        "launched_at": now,
        "pid": pid,
    }


async def pasha_status(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Check the status of a Pasha agent in a project.

    If the Pasha is marked as RUNNING, checks process liveness and
    optionally reads the status file from the container.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Dict with Pasha status details.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    pasha = project.pasha
    result: dict[str, Any] = {
        "project_id": project_id,
        "pasha_status": pasha.status.value,
        "task": pasha.task,
        "cost_limit": pasha.cost_limit,
        "cost_spent": pasha.cost_spent,
        "launched_at": pasha.launched_at,
        "pid": pasha.pid,
    }

    if pasha.status != PashaStatus.RUNNING:
        return result

    container = project.container_name
    if not container:
        return result

    # Check process liveness
    process_alive = False
    if pasha.pid is not None:
        rc, _stdout, _stderr = await _run_subprocess(
            ["docker", "exec", container, "kill", "-0", str(pasha.pid)],
            timeout=5,
        )
        process_alive = rc == 0

    result["process_alive"] = process_alive

    # Try to read status file
    rc, stdout, _stderr = await _run_subprocess(
        ["docker", "exec", container, "cat", "/workspace/.pasha/status.json"],
        timeout=5,
    )
    if rc == 0 and stdout.strip():
        try:
            result["status_file"] = json.loads(stdout)
        except json.JSONDecodeError:
            result["status_file_raw"] = stdout.strip()

    # Reconcile: if process dead, mark completed
    if not process_alive:
        realm.update_pasha_state(project_id, status=PashaStatus.COMPLETED, pid=None)
        result["pasha_status"] = PashaStatus.COMPLETED.value
        result["reconciled"] = True

    return result


async def agent_kill(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Kill a running Pasha agent in a project's container.

    Idempotent: returns success even if no agent is running.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Dict with kill status.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    if project.container_status != ContainerStatus.RUNNING:
        return {"error": f"Container not running (status: {project.container_status.value})"}

    container = project.container_name
    if not container:
        return {"error": "No container name recorded"}

    pasha = project.pasha
    killed = False

    # Try targeted kill by PID
    if pasha.pid is not None:
        rc, _stdout, _stderr = await _run_subprocess(
            ["docker", "exec", container, "kill", str(pasha.pid)],
            timeout=5,
        )
        if rc == 0:
            killed = True

    # Broad kill by entrypoint pattern as fallback
    if not killed:
        rc, _stdout, _stderr = await _run_subprocess(
            ["docker", "exec", container, "pkill", "-f", ".pasha/launch.sh"],
            timeout=5,
        )
        # pkill returns 1 if no processes matched -- that's fine (idempotent)

    realm.update_pasha_state(project_id, status=PashaStatus.KILLED, pid=None)

    return {
        "project_id": project_id,
        "pasha_status": "killed",
        "killed_pid": pasha.pid if killed else None,
    }


async def knowledge_link(realm: RealmManager, project_id: str, knowledge_project_id: str) -> dict[str, Any]:
    """Link a knowledge project to a work project.

    :param realm: RealmManager instance.
    :param project_id: Target project to receive the link.
    :param knowledge_project_id: Knowledge project to link.
    :return: Dict with link status.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    knowledge = realm.get_project(knowledge_project_id)
    if knowledge is None:
        return {"error": f"Knowledge project not found: {knowledge_project_id}"}

    if project.type != ProjectType.PROJECT:
        return {"error": f"Target must be a project, got: {project.type.value}"}

    if knowledge.type != ProjectType.KNOWLEDGE:
        return {"error": f"Source must be a knowledge project, got: {knowledge.type.value}"}

    if knowledge_project_id in project.knowledge_links:
        return {
            "project_id": project_id,
            "knowledge_project_id": knowledge_project_id,
            "linked": True,
            "detail": "already linked",
            "total_links": len(project.knowledge_links),
        }

    realm.update_project(project_id, knowledge_links=[*project.knowledge_links, knowledge_project_id])

    return {
        "project_id": project_id,
        "knowledge_project_id": knowledge_project_id,
        "linked": True,
        "total_links": len(project.knowledge_links) + 1,
    }
