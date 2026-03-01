"""Golden Trace models for agent-reported observability (D84).

Defines trace entry structure and action types for per-spec
agent reasoning and decision logging.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceActionType(enum.StrEnum):
    """Action types for Golden Trace entries."""

    command_executed = "command_executed"
    file_written = "file_written"
    file_read = "file_read"
    decision_made = "decision_made"
    tool_called = "tool_called"
    error_encountered = "error_encountered"
    escalation_sent = "escalation_sent"
    feedback_received = "feedback_received"
    spec_transitioned = "spec_transitioned"
    test_result = "test_result"
    reasoning = "reasoning"


class TraceEntry(BaseModel):
    """A single Golden Trace entry recorded by an agent."""

    project_id: str
    spec_id: str
    agent_role: str
    action_type: str
    summary: str
    detail: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
