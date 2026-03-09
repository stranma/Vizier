"""Project initialization tool.

Creates new projects by cloning or scaffolding a repo, injecting
devcontainer config from a template repo, and writing Vizier metadata
(sentinel/config) from bundled templates.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)

_PROJECT_ID_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_PROJECT_ID_MAX_LEN = 63
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_SUPPORTED_LANGUAGES = {"python"}


def _validate_project_id(project_id: str) -> str | None:
    """Validate project_id format. Returns error message or None if valid."""
    if not project_id:
        return "project_id must not be empty"
    if len(project_id) > _PROJECT_ID_MAX_LEN:
        return f"project_id must be at most {_PROJECT_ID_MAX_LEN} characters"
    if not _PROJECT_ID_RE.match(project_id):
        return "project_id must contain only lowercase alphanumeric characters and hyphens, and must start/end with alphanumeric"
    return None


def _substitute_template(content: str, variables: dict[str, str]) -> str:
    """Replace ``{{key}}`` placeholders in template content."""
    for key, value in variables.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def _copy_template_dir(src: Path, dst: Path, variables: dict[str, str]) -> None:
    """Recursively copy a template directory, substituting variables in text files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_template_dir(item, target, variables)
        else:
            content = item.read_text()
            content = _substitute_template(content, variables)
            target.write_text(content)


async def _fetch_devcontainer(repo: str, dest: Path) -> bool:
    """Sparse-clone a template repo and copy ``.devcontainer/`` into dest.

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


async def project_init(
    config: ServerConfig,
    project_id: str,
    source: str,
    language: str,
    git_url: str | None = None,
    project_name: str | None = None,
    devcontainer_repo: str = "stranma/claude-code-python-template",
) -> dict[str, Any]:
    """Initialize a new project with repo, devcontainer, and Vizier metadata.

    :param config: Server configuration.
    :param project_id: Unique project identifier (alphanumeric + hyphens, max 63 chars).
    :param source: "clone" or "scaffold".
    :param language: Template language ("python" for v1).
    :param git_url: Git URL to clone (required when source="clone").
    :param project_name: Display name, defaults to project_id.
    :param devcontainer_repo: GitHub repo for .devcontainer/ template.
    :return: Dict with project_id, source, repo_dir, devcontainer, sentinel_config, project_config.
    """
    # Validate inputs
    id_error = _validate_project_id(project_id)
    if id_error:
        return {"error": id_error}

    if source not in ("clone", "scaffold"):
        return {"error": f"Invalid source: {source}. Must be 'clone' or 'scaffold'"}

    if source == "clone" and not git_url:
        return {"error": "git_url is required when source='clone'"}

    if language not in _SUPPORTED_LANGUAGES:
        return {"error": f"Unsupported language: {language}. Supported: {sorted(_SUPPORTED_LANGUAGES)}"}

    template_dir = _TEMPLATES_DIR / language
    if not template_dir.exists():
        return {"error": f"Template directory not found for language: {language}"}

    if project_name is None:
        project_name = project_id

    assert config.projects_dir is not None
    assert config.repos_dir is not None
    project_meta_dir = config.projects_dir / project_id
    repo_dir = config.repos_dir / project_id

    if project_meta_dir.exists():
        return {"error": f"Project metadata directory already exists: {project_id}"}
    if repo_dir.exists():
        return {"error": f"Repository directory already exists: {project_id}"}

    created_dirs: list[Path] = []
    try:
        # Clone or scaffold
        config.repos_dir.mkdir(parents=True, exist_ok=True)
        if source == "clone":
            proc = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                git_url,
                str(repo_dir),  # type: ignore[arg-type]
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                return {"error": f"git clone failed: {stderr.decode().strip()}"}
            created_dirs.append(repo_dir)
        else:
            repo_dir.mkdir(parents=True)
            created_dirs.append(repo_dir)
            proc = await asyncio.create_subprocess_exec(
                "git",
                "init",
                str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(f"git init failed: {stderr.decode().strip()}")

        # Fetch devcontainer
        devcontainer_ok = await _fetch_devcontainer(devcontainer_repo, repo_dir)

        # Write Vizier metadata
        project_meta_dir.mkdir(parents=True)
        created_dirs.append(project_meta_dir)
        (project_meta_dir / "specs").mkdir()

        variables = {"project_name": project_name, "project_id": project_id}
        _copy_template_dir(template_dir, project_meta_dir, variables)

        sentinel_path = project_meta_dir / "sentinel.yaml"
        config_path = project_meta_dir / "config.yaml"

        return {
            "project_id": project_id,
            "source": source,
            "repo_dir": str(repo_dir),
            "devcontainer": devcontainer_ok,
            "sentinel_config": str(sentinel_path),
            "project_config": str(config_path),
        }

    except Exception:
        # Cleanup on failure
        for d in reversed(created_dirs):
            shutil.rmtree(d, ignore_errors=True)
        raise
