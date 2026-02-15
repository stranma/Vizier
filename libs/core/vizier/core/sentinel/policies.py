"""Sentinel policy models: requests, decisions, results."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PolicyDecision(StrEnum):
    """Outcome of a policy evaluation."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ABSTAIN = "ABSTAIN"


class ToolCallRequest(BaseModel):
    """A tool call to be evaluated by Sentinel."""

    tool: str
    args: dict = Field(default_factory=dict)
    command: str = ""
    agent_role: str = ""
    spec_id: str = ""


class SentinelResult(BaseModel):
    """Result from the Sentinel evaluation pipeline."""

    decision: PolicyDecision
    reason: str = ""
    policy: str = ""
    cost_usd: float = 0.0
