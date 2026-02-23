"""Budget tracking models for cost visibility.

Defines event types, budget events, and summary aggregations
for tracking agent resource consumption per project.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class BudgetEventType(enum.StrEnum):
    """Common budget event categories."""

    haiku_eval = "haiku_eval"
    spec_attempt = "spec_attempt"
    web_fetch = "web_fetch"
    custom = "custom"


class BudgetEvent(BaseModel):
    """A single cost event recorded against a project."""

    project_id: str
    spec_id: str | None = None
    event_type: str
    cost_estimate: float
    agent_role: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BudgetSummary(BaseModel):
    """Aggregated cost summary for a project."""

    project_id: str
    total_cost: float
    event_count: int
    by_event_type: dict[str, float]
    by_spec: dict[str, float]
    events: list[dict[str, Any]] = Field(default_factory=list)
