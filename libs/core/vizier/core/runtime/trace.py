"""Golden Trace: per-spec JSONL event log (D57)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class TraceLogger:
    """Appends structured events to a trace.jsonl file.

    Events are always stored in-memory for testing. If a file path is provided,
    events are also appended to disk as JSONL.

    :param trace_path: Optional filesystem path for persistent trace output.
    """

    def __init__(self, trace_path: Path | None = None) -> None:
        self._path = trace_path
        self._entries: list[dict[str, Any]] = []

    def log(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Append an event to the trace.

        :param event_type: Event type identifier (e.g. "tool_call", "run_start").
        :param data: Additional event data.
        """
        entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event_type,
            **(data or {}),
        }
        self._entries.append(entry)

        if self._path is not None:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except OSError:
                logger.warning("Failed to write trace entry to %s", self._path)

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Return all logged entries (useful for testing)."""
        return list(self._entries)
