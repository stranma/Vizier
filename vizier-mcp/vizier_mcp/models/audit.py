"""Audit entry model for automatic MCP tool call interception (D84).

Captures full kwargs and return values of every MCP tool call
for the Imperial Spymaster observability layer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """A single audit entry capturing an MCP tool call with full I/O."""

    tool_name: str
    kwargs: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: str = ""
    duration_ms: float = 0.0
    project_id: str = ""
    spec_id: str = ""
    agent_role: str = ""
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
