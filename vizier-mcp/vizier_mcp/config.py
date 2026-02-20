"""Server configuration loader.

Loads vizier-mcp server config from YAML or environment variables.
See ARCHITECTURE.md section 3.3 for the config schema.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class SentinelConfig(BaseModel):
    """Sentinel subsystem configuration."""

    default_policy: str = "strict"
    haiku_model: str = "claude-haiku-4-5-20251001"
    sentinel_learning: bool = False
    learning_threshold: int = 3


class ServerConfig(BaseModel):
    """Top-level MCP server configuration."""

    vizier_root: Path = Field(default_factory=lambda: Path(os.environ.get("VIZIER_ROOT", "/data/vizier")))
    projects_dir: Path | None = None
    sentinel: SentinelConfig = Field(default_factory=SentinelConfig)
    file_locking: bool = True
    startup_recovery: bool = True
    claim_timeout: int = 30

    def model_post_init(self, __context: object) -> None:
        """Set projects_dir default based on vizier_root."""
        if self.projects_dir is None:
            self.projects_dir = self.vizier_root / "projects"


def load_config(config_path: Path | None = None) -> ServerConfig:
    """Load server configuration from a YAML file or defaults.

    :param config_path: Optional path to config YAML. Falls back to defaults.
    :return: Validated ServerConfig instance.
    """
    if config_path and config_path.exists():
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        return ServerConfig(**data)
    return ServerConfig()
