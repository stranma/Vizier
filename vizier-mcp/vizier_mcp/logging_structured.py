"""Structured JSONL logging for the Vizier MCP server.

Writes tool call events, spec transitions, sentinel decisions, and errors
to a rotating JSONL log file at ``{vizier_root}/logs/vizier-mcp.jsonl``.

Thread-safe: each write opens, appends, and closes the file.
Log rotation: when the active file exceeds ``max_size_bytes``, it is renamed
with a numeric suffix and a new file is started. Old files beyond
``max_files`` are deleted.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

LOG_FILENAME = "vizier-mcp.jsonl"


class StructuredLogger:
    """Append-only JSONL logger with size-based rotation.

    :param log_dir: Directory for log files.
    :param max_size_bytes: Rotate when file exceeds this size.
    :param max_files: Number of rotated files to keep.
    """

    def __init__(
        self,
        log_dir: Path,
        max_size_bytes: int = 10 * 1024 * 1024,
        max_files: int = 5,
    ) -> None:
        self._log_dir = log_dir
        self._max_size_bytes = max_size_bytes
        self._max_files = max_files
        self._lock = threading.Lock()
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        """Path to the active log file."""
        return self._log_dir / LOG_FILENAME

    def log(
        self,
        level: str,
        module: str,
        event: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Write a single JSONL entry.

        :param level: Log level (INFO, ERROR, WARN, DEBUG).
        :param module: Source module name.
        :param event: Event type (tool_call, tool_error, spec_transition, etc.).
        :param data: Arbitrary event data.
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "module": module,
            "event": event,
            "data": data or {},
        }
        line = json.dumps(entry, default=str) + "\n"

        with self._lock:
            self._maybe_rotate()
            try:
                with open(self.log_path, "a") as f:
                    f.write(line)
            except OSError:
                logger.exception("Failed to write structured log entry")

    def log_tool_call(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Log a tool call event with timing."""
        merged = {"tool": tool_name, "duration_ms": round(duration_ms, 2), "success": success}
        if data:
            merged.update(data)
        self.log(
            level="INFO" if success else "ERROR",
            module="server",
            event="tool_call" if success else "tool_error",
            data=merged,
        )

    def _maybe_rotate(self) -> None:
        """Rotate the log file if it exceeds the size limit."""
        try:
            if not self.log_path.exists():
                return
            size = self.log_path.stat().st_size
        except OSError:
            return

        if size < self._max_size_bytes:
            return

        for i in range(self._max_files, 0, -1):
            src = self._log_dir / f"{LOG_FILENAME}.{i}"
            if i == self._max_files:
                if src.exists():
                    src.unlink()
            else:
                dst = self._log_dir / f"{LOG_FILENAME}.{i + 1}"
                if src.exists():
                    src.rename(dst)

        dest = self._log_dir / f"{LOG_FILENAME}.1"
        try:
            self.log_path.rename(dest)
        except OSError:
            logger.exception("Failed to rotate log file")

    def read_entries(
        self,
        level: str | None = None,
        module: str | None = None,
        event: str | None = None,
        since_minutes: int = 60,
        limit: int = 100,
        spec_id: str | None = None,
    ) -> dict[str, Any]:
        """Read and filter log entries.

        :param level: Filter by log level.
        :param module: Filter by module name.
        :param event: Filter by event type.
        :param since_minutes: Only entries from the last N minutes.
        :param limit: Maximum entries to return.
        :param spec_id: Filter by spec_id in entry data.
        :return: {"entries": list, "total_matched": int, "truncated": bool}
        """
        cutoff = time.time() - (since_minutes * 60)
        matched: list[dict[str, Any]] = []

        for path in self._log_files():
            try:
                with open(path) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not self._matches(entry, level, module, event, cutoff, spec_id):
                            continue
                        matched.append(entry)
            except OSError:
                continue

        matched.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
        total = len(matched)
        truncated = total > limit
        return {
            "entries": matched[:limit],
            "total_matched": total,
            "truncated": truncated,
        }

    def _log_files(self) -> list[Path]:
        """Return log files in order: active first, then .1, .2, etc."""
        files = []
        if self.log_path.exists():
            files.append(self.log_path)
        for i in range(1, self._max_files + 1):
            p = self._log_dir / f"{LOG_FILENAME}.{i}"
            if p.exists():
                files.append(p)
        return files

    @staticmethod
    def _matches(
        entry: dict[str, Any],
        level: str | None,
        module: str | None,
        event: str | None,
        cutoff: float,
        spec_id: str | None,
    ) -> bool:
        """Check if an entry matches the given filters."""
        ts_str = entry.get("timestamp", "")
        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str).timestamp()
                if ts < cutoff:
                    return False
            except (ValueError, TypeError):
                pass

        if level and entry.get("level", "").upper() != level.upper():
            return False
        if module and entry.get("module", "") != module:
            return False
        if event and entry.get("event", "") != event:
            return False
        if spec_id:
            data = entry.get("data", {})
            if data.get("spec_id") != spec_id:
                return False
        return True


_logger_instance: StructuredLogger | None = None
_instance_lock = threading.Lock()


def get_logger(
    log_dir: Path | None = None, max_size_bytes: int = 10 * 1024 * 1024, max_files: int = 5
) -> StructuredLogger:
    """Get or create the singleton StructuredLogger.

    :param log_dir: Directory for log files. Required on first call.
    :param max_size_bytes: Max file size before rotation.
    :param max_files: Number of rotated files to keep.
    :return: StructuredLogger instance.
    """
    global _logger_instance
    with _instance_lock:
        if _logger_instance is None:
            if log_dir is None:
                log_dir = Path(os.environ.get("VIZIER_ROOT", "/data/vizier")) / "logs"
            _logger_instance = StructuredLogger(log_dir, max_size_bytes, max_files)
        return _logger_instance


def reset_logger() -> None:
    """Reset the singleton logger (for testing)."""
    global _logger_instance
    with _instance_lock:
        _logger_instance = None
