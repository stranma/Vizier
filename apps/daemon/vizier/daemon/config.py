"""Server configuration loader for the Vizier daemon."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class AutonomyConfig(BaseModel):
    """Progressive autonomy rollout configuration (D44)."""

    stage: int = Field(default=1, ge=1, le=4)
    auto_approve_plugins: list[str] = Field(default_factory=list)
    stage_history: list[dict[str, str]] = Field(default_factory=list)


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    token: str = ""
    allowed_user_ids: list[int] = Field(default_factory=list)


class DaemonConfig(BaseModel):
    """Server-wide daemon configuration."""

    vizier_root: str = "/opt/vizier"
    workspaces_dir: str = "workspaces"
    reports_dir: str = "reports"
    ea_data_dir: str = "ea"
    security_dir: str = "security"
    checkout_dir: str = "checkout"
    max_concurrent_agents: int = Field(default=5, ge=1)
    reconciliation_interval_seconds: int = Field(default=15, ge=1)
    heartbeat_path: str = "heartbeat.json"
    monthly_budget_usd: float = Field(default=100.0, gt=0)
    autonomy: AutonomyConfig = Field(default_factory=AutonomyConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    log_rotation_max_bytes: int = Field(default=10 * 1024 * 1024)
    log_rotation_backup_count: int = Field(default=5)
    health_check_port: int = Field(default=8080, ge=1024, le=65535)
    azure_vault_url: str = ""


class ProjectEntry(BaseModel):
    """A registered project in the daemon."""

    name: str
    repo_url: str = ""
    local_path: str = ""
    plugin: str = "software"
    active: bool = True


class ProjectRegistry(BaseModel):
    """Registry of all managed projects."""

    projects: list[ProjectEntry] = Field(default_factory=list)

    def get(self, name: str) -> ProjectEntry | None:
        """Look up a project by name."""
        for p in self.projects:
            if p.name == name:
                return p
        return None

    def add(self, entry: ProjectEntry) -> None:
        """Add a project to the registry."""
        existing = self.get(entry.name)
        if existing is not None:
            raise ValueError(f"Project '{entry.name}' already registered")
        self.projects.append(entry)

    def remove(self, name: str) -> bool:
        """Remove a project by name."""
        for i, p in enumerate(self.projects):
            if p.name == name:
                self.projects.pop(i)
                return True
        return False

    def active_projects(self) -> list[ProjectEntry]:
        """Return only active projects."""
        return [p for p in self.projects if p.active]


def load_daemon_config(config_path: str | Path) -> DaemonConfig:
    """Load daemon configuration from YAML file with env var substitution.

    :param config_path: Path to config.yaml file.
    :returns: Parsed daemon configuration.
    """
    path = Path(config_path)
    if not path.exists():
        return DaemonConfig()

    content = path.read_text(encoding="utf-8")
    for key, value in os.environ.items():
        content = content.replace(f"${{{key}}}", value)

    data = yaml.safe_load(content)
    if not data:
        return DaemonConfig()

    return DaemonConfig(**data)


def load_project_registry(registry_path: str | Path) -> ProjectRegistry:
    """Load project registry from YAML file.

    :param registry_path: Path to projects.yaml file.
    :returns: Parsed project registry.
    """
    path = Path(registry_path)
    if not path.exists():
        return ProjectRegistry()

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        return ProjectRegistry()

    return ProjectRegistry(**data)


def save_project_registry(registry: ProjectRegistry, registry_path: str | Path) -> None:
    """Save project registry to YAML file using atomic write.

    :param registry: The registry to save.
    :param registry_path: Path to projects.yaml file.
    """
    path = Path(registry_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".yaml.tmp")
    data = registry.model_dump(mode="json")
    tmp_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    os.replace(str(tmp_path), str(path))
