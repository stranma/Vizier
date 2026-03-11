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
        }


class RealmState(BaseModel):
    """Persisted realm state, serialized to realm.json."""

    projects: dict[str, Project] = Field(default_factory=dict)
