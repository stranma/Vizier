"""EA data models for commitments, relationships, priorities, and tracking."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class CommitmentStatus(StrEnum):
    """Lifecycle states for commitments."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PriorityLevel(StrEnum):
    """Priority urgency levels."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Commitment(BaseModel):
    """A promise to a person with a deadline, optionally linked to a project."""

    id: str
    description: str
    promised_to: str
    deadline: datetime | None = None
    project: str | None = None
    status: CommitmentStatus = CommitmentStatus.PENDING
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)
    notes: str = ""


class Relationship(BaseModel):
    """Contact with context, open commitments, and interaction history."""

    id: str
    name: str
    role: str = ""
    open_commitments: list[str] = Field(default_factory=list)
    last_contact: datetime | None = None
    notes: str = ""
    created: datetime = Field(default_factory=datetime.utcnow)
    updated: datetime = Field(default_factory=datetime.utcnow)


class Priority(BaseModel):
    """A prioritized project or task with urgency level."""

    project: str
    reason: str = ""
    urgency: PriorityLevel = PriorityLevel.NORMAL


class PrioritiesConfig(BaseModel):
    """Sultan's priorities and standing instructions."""

    current_focus: str = ""
    priority_order: list[Priority] = Field(default_factory=list)
    standing_instructions: list[str] = Field(default_factory=list)


class BriefingConfig(BaseModel):
    """Configuration for morning briefings and proactive behaviors."""

    briefing_hour: int = Field(default=8, ge=0, le=23)
    briefing_minute: int = Field(default=0, ge=0, le=59)
    include_cost_summary: bool = True
    include_calendar: bool = True
    include_commitments: bool = True
    include_risks: bool = True


class CheckoutRecord(BaseModel):
    """Tracks a file checked out by the Sultan for direct editing."""

    file_path: str
    project: str
    checked_out_at: datetime = Field(default_factory=datetime.utcnow)
    original_commit: str = ""
    returned: bool = False
    returned_at: datetime | None = None


class CheckinRecord(BaseModel):
    """Record from a structured check-in interview."""

    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    new_contacts: list[str] = Field(default_factory=list)
    new_commitments: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    notes: str = ""


class FocusMode(BaseModel):
    """Focus mode state -- hold non-emergency notifications."""

    active: bool = False
    started_at: datetime | None = None
    duration_hours: float = 0
    held_messages: list[str] = Field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        """Check if focus mode has expired based on duration."""
        if not self.active or self.started_at is None:
            return True
        elapsed = (datetime.utcnow() - self.started_at).total_seconds() / 3600
        return elapsed >= self.duration_hours


class BudgetConfig(BaseModel):
    """Cost budget configuration for D33 enforcement."""

    monthly_budget_usd: float = Field(default=100.0, gt=0)
    alert_threshold: float = Field(default=0.8, gt=0, le=1.0)
    degrade_threshold: float = Field(default=1.0, gt=0)
    pause_threshold: float = Field(default=1.2, gt=0)
