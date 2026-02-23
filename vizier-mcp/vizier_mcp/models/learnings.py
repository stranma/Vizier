"""Failure learnings models for retry context injection.

Defines learning categories, learning records, and match results
for extracting failure context from rejected/stuck specs and
injecting it into retry attempts.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class LearningCategory(enum.StrEnum):
    """Categories of failure learnings."""

    test_failure = "test_failure"
    lint_failure = "lint_failure"
    type_error = "type_error"
    spec_ambiguity = "spec_ambiguity"
    sentinel_denied = "sentinel_denied"
    timeout = "timeout"
    impossible = "impossible"


class Learning(BaseModel):
    """A single failure learning extracted from a rejected or stuck spec."""

    learning_id: str
    source_spec_id: str
    project_id: str
    category: str
    summary: str
    detail: str = ""
    keywords: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LearningMatch(BaseModel):
    """A learning matched to a target spec for context injection."""

    learning: dict[str, Any]
    match_reason: str
