"""Filesystem event models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    """Filesystem event types."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


class FileEvent(BaseModel):
    """A filesystem event dispatched by the watcher or reconciler."""

    event_type: EventType
    path: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_synthetic: bool = False
