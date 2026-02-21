"""Project configuration tool.

Loads project config.yaml and returns it as a dict. Replaces the v1
plugin framework (D75) -- project_get_config provides type, language,
framework, test/lint commands, and custom settings.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import yaml
from pydantic import ValidationError

from vizier_mcp.models.orchestration import ProjectConfig

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)


def project_get_config(
    config: ServerConfig,
    project_id: str,
) -> dict:
    """Get project configuration including plugin type and settings.

    Loads {projects_dir}/{project_id}/config.yaml and returns all fields.
    Missing config.yaml returns a sensible default with null type and
    empty settings.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :return: Project config dict or {"error": str}.
    """
    assert config.projects_dir is not None
    project_dir = config.projects_dir / project_id
    if not str(project_dir.resolve()).startswith(str(config.projects_dir.resolve())):
        return {"error": f"Invalid project ID: '{project_id}'"}
    if not project_dir.is_dir():
        return {"error": f"Project '{project_id}' not found"}

    config_path = project_dir / "config.yaml"
    if not config_path.exists():
        return ProjectConfig().model_dump()

    try:
        raw = yaml.safe_load(config_path.read_text())
    except yaml.YAMLError as exc:
        return {"error": f"Malformed config.yaml: {exc}"}

    if not isinstance(raw, dict):
        return ProjectConfig().model_dump()

    try:
        project_config = ProjectConfig(**raw)
    except (ValidationError, TypeError) as exc:
        return {"error": f"Invalid config.yaml: {exc}"}

    return project_config.model_dump()
