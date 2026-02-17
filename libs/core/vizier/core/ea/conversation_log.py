"""Conversation log for EA multi-turn history.

Persists conversation turns as JSONL for efficient append-only storage.
Supports rotation to prevent unbounded growth.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_LINES_BEFORE_ROTATION = 1000


class ConversationTurn(BaseModel):
    """A single turn in the EA conversation.

    :param role: Speaker -- ``"user"`` for Sultan messages, ``"assistant"`` for EA responses.
    :param content: Raw message text.
    :param category: MessageCategory value (e.g. ``"general"``, ``"status"``). Empty string when
        category is unknown or not relevant.
    :param metadata: Optional key-value pairs for transport-layer context, such as
        ``{"reply_to": "<quoted text>"}`` from Telegram reply forwarding.
    :param timestamp: UTC time of the turn. Defaults to the current time at construction.
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    role: Literal["user", "assistant"]
    content: str
    category: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)


class ConversationLog:
    """Append-only JSONL conversation log with rotation.

    :param log_dir: Directory for conversation log files (typically ea/sessions/).
    :param max_turns: Maximum recent turns to return from :meth:`recent`.
    """

    def __init__(self, log_dir: Path, max_turns: int = 20) -> None:
        self._log_dir = log_dir
        self._max_turns = max_turns
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _current_log_path(self) -> Path:
        return self._log_dir / "conversation.jsonl"

    def append(self, turn: ConversationTurn) -> None:
        """Append a turn to the conversation log.

        :param turn: The conversation turn to persist.
        """
        self._rotate_if_needed()
        path = self._current_log_path()
        line = turn.model_dump_json() + "\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    def recent(self, n: int | None = None) -> list[ConversationTurn]:
        """Load the most recent N turns from the log.

        :param n: Number of turns to return. Defaults to max_turns.
        :returns: List of recent turns in chronological order.
        """
        if n is None:
            n = self._max_turns

        path = self._current_log_path()
        if not path.exists():
            return []

        turns: list[ConversationTurn] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(ConversationTurn.model_validate_json(line))
            except (json.JSONDecodeError, ValueError):
                logger.warning("Skipping corrupt conversation log line")
                continue

        return turns[-n:]

    def _rotate_if_needed(self) -> None:
        """Rotate log file if it exceeds the line limit."""
        path = self._current_log_path()
        if not path.exists():
            return

        try:
            with open(path, encoding="utf-8") as f:
                line_count = sum(1 for _ in f)
        except OSError:
            return

        if line_count >= MAX_LINES_BEFORE_ROTATION:
            backup = path.with_suffix(".jsonl.1")
            if backup.exists():
                backup.unlink()
            path.rename(backup)
