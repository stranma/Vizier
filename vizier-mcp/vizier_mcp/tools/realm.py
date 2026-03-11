"""Realm management tools for Vizier v2.

Provides MCP tools to list, create, and inspect projects in the realm.

Security note: All subprocess calls use create_subprocess_exec (not shell)
to prevent command injection. Arguments are passed as separate list elements.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vizier_mcp.models.realm import Project, ProjectType

if TYPE_CHECKING:
    from vizier_mcp.realm import RealmManager

logger = logging.getLogger(__name__)

_PROJECT_ID_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_PROJECT_ID_MAX_LEN = 63


def _validate_project_id(project_id: str) -> str | None:
    """Validate project_id format. Returns error message or None if valid."""
    if not project_id:
        return "project_id must not be empty"
    if len(project_id) > _PROJECT_ID_MAX_LEN:
        return f"project_id must be at most {_PROJECT_ID_MAX_LEN} characters"
    if not _PROJECT_ID_RE.match(project_id):
        return "project_id must contain only lowercase alphanumeric characters and hyphens, and must start/end with alphanumeric"
    return None


async def _fetch_devcontainer(repo: str, dest: Path) -> bool:
    """Sparse-clone a template repo and copy ``.devcontainer/`` into dest.

    Uses create_subprocess_exec (no shell) for safe subprocess execution.

    :param repo: GitHub repo in ``owner/name`` format.
    :param dest: Target repo directory to copy ``.devcontainer/`` into.
    :return: True if devcontainer was successfully copied.
    """
    url = f"https://github.com/{repo}.git"
    tmp_dir = Path(tempfile.mkdtemp(prefix="vizier-devcontainer-"))
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            url,
            str(tmp_dir / "repo"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning("Failed to clone devcontainer repo %s: %s", repo, stderr.decode())
            return False

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(tmp_dir / "repo"),
            "sparse-checkout",
            "set",
            ".devcontainer",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        if proc.returncode != 0:
            logger.warning("Failed to set sparse-checkout for %s", repo)
            return False

        cloned_devcontainer = tmp_dir / "repo" / ".devcontainer"
        if not cloned_devcontainer.exists():
            logger.warning("No .devcontainer/ found in %s", repo)
            return False

        target_devcontainer = dest / ".devcontainer"
        if target_devcontainer.exists():
            shutil.rmtree(target_devcontainer)
        shutil.copytree(cloned_devcontainer, target_devcontainer)
        return True
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def realm_list_projects(realm: RealmManager, type_filter: str | None = None) -> dict[str, Any]:
    """List all projects and knowledge projects in the realm.

    :param realm: RealmManager instance.
    :param type_filter: Optional filter: "project" or "knowledge".
    :return: Dict with projects list and count.
    """
    projects = realm.list_projects(type_filter)
    return {
        "projects": projects,
        "count": len(projects),
    }


async def realm_create_project(
    realm: RealmManager,
    project_id: str,
    project_type: str = "project",
    git_url: str | None = None,
    template: str = "stranma/claude-code-python-template",
) -> dict[str, Any]:
    """Initialize a project in the realm.

    Creates the project entry, clones or scaffolds the repo, and
    copies devcontainer config from the template.

    Uses create_subprocess_exec (no shell) for safe subprocess execution.

    :param realm: RealmManager instance.
    :param project_id: Unique project identifier.
    :param project_type: "project" or "knowledge".
    :param git_url: Git URL to clone. If None, scaffolds an empty repo.
    :param template: GitHub repo for .devcontainer/ template.
    :return: Dict with project details or error.
    """
    id_error = _validate_project_id(project_id)
    if id_error:
        return {"error": id_error}

    try:
        pt = ProjectType(project_type)
    except ValueError:
        return {"error": f"Invalid project_type: {project_type}. Must be 'project' or 'knowledge'"}

    if realm.get_project(project_id) is not None:
        return {"error": f"Project already exists: {project_id}"}

    repos_dir = realm.repos_dir
    repo_dir = repos_dir / project_id

    if repo_dir.exists():
        return {"error": f"Repository directory already exists: {project_id}"}

    repos_dir.mkdir(parents=True, exist_ok=True)

    try:
        if git_url:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                git_url,
                str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                return {"error": f"git clone failed: {stderr.decode().strip()}"}
        else:
            repo_dir.mkdir(parents=True)
            proc = await asyncio.create_subprocess_exec(
                "git",
                "init",
                str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                shutil.rmtree(repo_dir, ignore_errors=True)
                return {"error": f"git init failed: {stderr.decode().strip()}"}

        devcontainer_ok = await _fetch_devcontainer(template, repo_dir)

        project = Project(
            id=project_id,
            type=pt,
            git_url=git_url,
            template=template,
        )
        realm.add_project(project)

        return {
            "project_id": project_id,
            "type": pt.value,
            "repo_dir": str(repo_dir),
            "devcontainer": devcontainer_ok,
            "git_url": git_url,
            "template": template,
        }

    except Exception:
        shutil.rmtree(repo_dir, ignore_errors=True)
        raise


def realm_get_project(realm: RealmManager, project_id: str) -> dict[str, Any]:
    """Get project config, status, and details.

    :param realm: RealmManager instance.
    :param project_id: Project identifier.
    :return: Project details dict or error.
    """
    project = realm.get_project(project_id)
    if project is None:
        return {"error": f"Project not found: {project_id}"}

    result = project.to_summary()
    result["repo_dir"] = str(realm.repos_dir / project_id)
    return result
