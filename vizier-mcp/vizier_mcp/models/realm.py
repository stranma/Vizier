"""Realm and project models for Vizier v2.

The realm is everything Vizier manages: projects (code repos in devcontainers)
and knowledge projects (reference repos, read-only).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProjectType(StrEnum):
    """Type of project in the realm."""

    PROJECT = "project"
    KNOWLEDGE = "knowledge"


class ContainerStatus(StrEnum):
    """Container lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class PashaStatus(StrEnum):
    """Pasha agent lifecycle states."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


class PashaManifest(BaseModel):
    """Schema for .pasha/manifest.json in project templates."""

    name: str
    version: str = "1.0.0"
    runtime: str = "hermes"
    entrypoint: str = ".pasha/launch.sh"
    soul: str = ".pasha/SOUL.md"
    status_file: str = ".pasha/status.json"
    capabilities: list[str] = Field(default_factory=list)
    env_requires: list[str] = Field(default_factory=list)


class PashaState(BaseModel):
    """Tracked state of a Pasha agent within a project."""

    status: PashaStatus = PashaStatus.IDLE
    task: str | None = None
    acceptance_criteria: list[str] = Field(default_factory=list)
    cost_limit: float | None = None
    cost_spent: float = 0.0
    launched_at: str | None = None
    pid: int | None = None


class Project(BaseModel):
    """A project in the realm -- a code repository inside a devcontainer."""

    id: str
    type: ProjectType = ProjectType.PROJECT
    git_url: str | None = None
    template: str = "stranma/claude-code-python-template"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    status: str = "active"
    container_name: str | None = None
    container_status: ContainerStatus = ContainerStatus.STOPPED
    knowledge_links: list[str] = Field(default_factory=list)
    pasha: PashaState = Field(default_factory=PashaState)

    def to_summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for API responses."""
        return {
            "id": self.id,
            "type": self.type.value,
            "git_url": self.git_url,
            "template": self.template,
            "created_at": self.created_at,
            "status": self.status,
            "container_status": self.container_status.value,
            "knowledge_links": self.knowledge_links,
            "pasha_status": self.pasha.status.value,
            "pasha_task": self.pasha.task,
        }


class RealmState(BaseModel):
    """Persisted realm state, serialized to realm.json."""

    projects: dict[str, Project] = Field(default_factory=dict)
