"""Spec data models and state machine transitions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SpecStatus(StrEnum):
    """Spec lifecycle states matching FILE_PROTOCOL.md."""

    DRAFT = "DRAFT"
    SCOUTED = "SCOUTED"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    DONE = "DONE"
    REJECTED = "REJECTED"
    STUCK = "STUCK"
    DECOMPOSED = "DECOMPOSED"
    INTERRUPTED = "INTERRUPTED"


class SpecComplexity(StrEnum):
    """Spec complexity levels used by model router."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


VALID_TRANSITIONS: dict[SpecStatus, list[SpecStatus]] = {
    SpecStatus.DRAFT: [SpecStatus.SCOUTED, SpecStatus.READY, SpecStatus.DECOMPOSED],
    SpecStatus.SCOUTED: [SpecStatus.DECOMPOSED],
    SpecStatus.READY: [SpecStatus.IN_PROGRESS],
    SpecStatus.IN_PROGRESS: [SpecStatus.REVIEW, SpecStatus.STUCK, SpecStatus.INTERRUPTED],
    SpecStatus.REVIEW: [SpecStatus.DONE, SpecStatus.REJECTED],
    SpecStatus.REJECTED: [SpecStatus.IN_PROGRESS],
    SpecStatus.STUCK: [SpecStatus.DECOMPOSED],
    SpecStatus.INTERRUPTED: [SpecStatus.READY],
    SpecStatus.DONE: [],
    SpecStatus.DECOMPOSED: [],
}


class SpecFrontmatter(BaseModel):
    """YAML frontmatter for spec files."""

    id: str
    status: SpecStatus = SpecStatus.DRAFT
    priority: int = Field(default=1, ge=1)
    complexity: SpecComplexity = SpecComplexity.MEDIUM
    retries: int = Field(default=0, ge=0)
    max_retries: int = Field(default=10, ge=1)
    parent: str | None = None
    plugin: str = "software"
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: str | None = None
    requires_approval: bool = False


class Spec(BaseModel):
    """Complete spec: frontmatter + markdown content."""

    frontmatter: SpecFrontmatter
    content: str = ""
    file_path: str | None = None
