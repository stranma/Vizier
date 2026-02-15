"""Structured logging models for agent invocations."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentLogEntry(BaseModel):
    """A single agent invocation log entry for agent-log.jsonl."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    spec_id: str | None = None
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    cost_usd: float = 0.0
    result: str = ""
    project: str = ""
