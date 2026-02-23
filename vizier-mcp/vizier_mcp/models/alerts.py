"""Alert models for event-driven notifications.

Defines alert types and severity levels for budget threshold
violations and other system events requiring operator attention.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AlertSeverity(enum.StrEnum):
    """Alert severity levels."""

    warning = "warning"
    critical = "critical"


class AlertType(enum.StrEnum):
    """Known alert types."""

    budget_soft_limit = "budget_soft_limit"
    budget_hard_limit = "budget_hard_limit"


class AlertData(BaseModel):
    """A system alert requiring operator attention."""

    alert_type: str
    project_id: str
    message: str
    severity: AlertSeverity
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    acknowledged: bool = False
    data: dict[str, Any] = Field(default_factory=dict)
