"""Spec, SpecStatus, and SpecMetadata models.

Defines the core data types for the spec lifecycle state machine.
See ARCHITECTURE.md section 10 for the state diagram.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class SpecStatus(enum.StrEnum):
    """Valid spec states in the v1 state machine."""

    DRAFT = "DRAFT"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    REJECTED = "REJECTED"
    DONE = "DONE"
    STUCK = "STUCK"
    INTERRUPTED = "INTERRUPTED"


VALID_TRANSITIONS: dict[SpecStatus, list[SpecStatus]] = {
    SpecStatus.DRAFT: [SpecStatus.READY],
    SpecStatus.READY: [SpecStatus.IN_PROGRESS, SpecStatus.STUCK],
    SpecStatus.IN_PROGRESS: [SpecStatus.REVIEW, SpecStatus.INTERRUPTED],
    SpecStatus.REVIEW: [SpecStatus.DONE, SpecStatus.REJECTED],
    SpecStatus.REJECTED: [SpecStatus.READY, SpecStatus.STUCK],
    SpecStatus.INTERRUPTED: [SpecStatus.READY],
    SpecStatus.DONE: [],
    SpecStatus.STUCK: [],
}


def is_valid_transition(from_status: SpecStatus, to_status: SpecStatus) -> bool:
    """Check if a state transition is valid per the v1 state machine."""
    return to_status in VALID_TRANSITIONS.get(from_status, [])


class SpecMetadata(BaseModel):
    """Mutable metadata tracked alongside a spec."""

    spec_id: str
    project_id: str
    title: str
    status: SpecStatus = SpecStatus.DRAFT
    complexity: str = "MEDIUM"
    assigned_agent: str | None = None
    retry_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    claimed_at: datetime | None = None
    depends_on: list[str] = Field(default_factory=list)


class Spec(BaseModel):
    """A complete spec: metadata + body content."""

    metadata: SpecMetadata
    body: str = ""
    artifacts: list[str] = Field(default_factory=list)
    criteria: list[str] = Field(default_factory=list)


class SpecSummary(BaseModel):
    """Lightweight spec representation for listing."""

    spec_id: str
    project_id: str
    title: str
    status: SpecStatus
    complexity: str
    retry_count: int
    assigned_agent: str | None = None


class SpecFeedback(BaseModel):
    """Quality Gate feedback on a spec."""

    spec_id: str
    verdict: str
    feedback: str
    reviewer: str = "quality_gate"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SpecTransitionRequest(BaseModel):
    """Request to transition a spec to a new state."""

    spec_id: str
    new_status: SpecStatus
    agent_role: str
    reason: str = ""


class SpecCreateRequest(BaseModel):
    """Request to create a new spec."""

    project_id: str
    title: str
    description: str
    complexity: str = "MEDIUM"
    artifacts: list[str] = Field(default_factory=list)
    criteria: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)


class SpecUpdateRequest(BaseModel):
    """Request to update mutable spec fields."""

    spec_id: str
    fields: dict[str, Any]
