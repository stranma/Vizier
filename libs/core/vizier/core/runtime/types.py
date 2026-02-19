"""Runtime type definitions for agent tool loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class StopReason(StrEnum):
    """Why the agent loop terminated."""

    COMPLETED = "completed"
    BUDGET_EXHAUSTED = "budget_exhausted"
    MAX_TURNS_REACHED = "max_turns_reached"
    ERROR = "error"


@dataclass
class ToolDefinition:
    """A tool available to an agent.

    :param name: Tool name (must match what Claude calls).
    :param description: Human-readable description for Claude's system prompt.
    :param input_schema: JSON Schema for the tool's input parameters.
    :param handler: Callable that executes the tool (called with **kwargs from tool input).
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any]


@dataclass
class ToolCallRecord:
    """Record of a single tool call for tracing."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_result: Any
    sentinel_decision: str = "ALLOW"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    duration_ms: int = 0


@dataclass
class RunResult:
    """Result of an agent run."""

    stop_reason: StopReason
    final_text: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    tokens_used: int = 0
    turns: int = 0
    error: str = ""
