"""Orchestration models: PingMessage, PingUrgency, ProjectConfig.

Defines data types for supervisor pings (D77) and project configuration.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class PingUrgency(enum.StrEnum):
    """Valid ping urgency levels (D77).

    QUESTION: Worker needs clarification from Pasha.
    BLOCKER: Worker is blocked and needs immediate help.
    IMPOSSIBLE: The spec itself is defective (D77 escape hatch).
    """

    QUESTION = "QUESTION"
    BLOCKER = "BLOCKER"
    IMPOSSIBLE = "IMPOSSIBLE"


class PingMessage(BaseModel):
    """A supervisor ping written by an inner agent (D77).

    Written as JSON to {spec_dir}/pings/{timestamp}-{urgency}.json.
    """

    spec_id: str
    urgency: PingUrgency
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectConfig(BaseModel):
    """Project configuration loaded from config.yaml.

    Replaces the v1 plugin framework (D75). Contains project type,
    language, framework, test/lint commands, and custom settings.
    """

    type: str | None = None
    language: str | None = None
    framework: str | None = None
    test_command: str | None = None
    lint_command: str | None = None
    type_command: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
