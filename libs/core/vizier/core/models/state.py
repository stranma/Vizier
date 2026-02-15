"""Runtime state models for state.json."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, Field


class ActiveAgent(BaseModel):
    """An active agent process."""

    pid: int
    since: datetime
    spec: str | None = None


class ProjectState(BaseModel):
    """Runtime state persisted to .vizier/state.json."""

    project: str
    plugin: str = "software"
    current_cycle: int = Field(default=0, ge=0)
    active_agents: dict[str, ActiveAgent] = Field(default_factory=dict)
    queue: list[str] = Field(default_factory=list)
    last_retrospective: datetime | None = None
