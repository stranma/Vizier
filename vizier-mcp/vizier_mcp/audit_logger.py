"""Audit logger for automatic MCP tool call interception (D84).

Captures full kwargs and return values of every MCP tool call.
Dual-write: global audit.jsonl + per-spec audit.jsonl when spec_id
is extractable from tool kwargs.

Thread-safe with size-based rotation on the global log.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path  # noqa: TC003 -- used at runtime in __init__ and properties
from typing import Any

from vizier_mcp.models.audit import AuditEntry

logger = logging.getLogger(__name__)

AUDIT_FILENAME = "audit.jsonl"


class AuditLogger:
    """Append-only audit logger with dual-write and rotation.

    :param audit_dir: Directory for the global audit log.
    :param projects_dir: Projects root for per-spec audit logs.
    :param max_size_bytes: Rotate global log when it exceeds this size.
    :param max_files: Number of rotated global log files to keep.
    :param max_output_chars: Truncate result values longer than this.
    """

    def __init__(
        self,
        audit_dir: Path,
        projects_dir: Path,
        max_size_bytes: int = 10 * 1024 * 1024,
        max_files: int = 5,
        max_output_chars: int = 4000,
    ) -> None:
        self._audit_dir = audit_dir
        self._projects_dir = projects_dir
        self._max_size_bytes = max_size_bytes
        self._max_files = max_files
        self._max_output_chars = max_output_chars
        self._lock = threading.Lock()
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    @property
    def global_log_path(self) -> Path:
        """Path to the global audit log file."""
        return self._audit_dir / AUDIT_FILENAME

    def record(self, entry: AuditEntry) -> None:
        """Write an audit entry to global log and optionally per-spec log.

        :param entry: The audit entry to record.
        """
        line = entry.model_dump_json() + "\n"

        with self._lock:
            self._maybe_rotate()
            try:
                with open(self.global_log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except OSError:
                logger.exception("Failed to write global audit entry")

        if entry.project_id and entry.spec_id:
            self._write_per_spec(entry.project_id, entry.spec_id, line)

    def build_entry(
        self,
        tool_name: str,
        kwargs: dict[str, Any],
        result: dict[str, Any] | None,
        success: bool,
        error: str,
        duration_ms: float,
    ) -> AuditEntry:
        """Build an AuditEntry from tool call data, extracting context from kwargs.

        :param tool_name: Name of the MCP tool called.
        :param kwargs: Tool call keyword arguments.
        :param result: Tool return value (may be truncated).
        :param success: Whether the call succeeded.
        :param error: Error message if failed.
        :param duration_ms: Call duration in milliseconds.
        :return: Populated AuditEntry.
        """
        project_id = str(kwargs.get("project_id", ""))
        spec_id = str(kwargs.get("spec_id", ""))
        agent_role = str(kwargs.get("agent_role", ""))

        truncated_result = self._truncate_result(result or {})

        return AuditEntry(
            tool_name=tool_name,
            kwargs=kwargs,
            result=truncated_result,
            success=success,
            error=error,
            duration_ms=round(duration_ms, 2),
            project_id=project_id,
            spec_id=spec_id,
            agent_role=agent_role,
        )

    def read_entries(
        self,
        project_id: str | None = None,
        spec_id: str | None = None,
        tool_name: str | None = None,
        agent_role: str | None = None,
        since_minutes: int | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Read and filter audit entries.

        If project_id and spec_id are both provided, reads from per-spec log.
        Otherwise reads from global log.

        :return: List of matching AuditEntry objects, newest first.
        """
        path = self._spec_audit_path(project_id, spec_id) if project_id and spec_id else self.global_log_path

        entries = self._read_file(path)

        if since_minutes is not None:
            from datetime import UTC, datetime, timedelta

            cutoff = datetime.now(UTC) - timedelta(minutes=since_minutes)
            entries = [e for e in entries if e.recorded_at >= cutoff]
        if project_id:
            entries = [e for e in entries if e.project_id == project_id]
        if spec_id:
            entries = [e for e in entries if e.spec_id == spec_id]
        if tool_name:
            entries = [e for e in entries if e.tool_name == tool_name]
        if agent_role:
            entries = [e for e in entries if e.agent_role == agent_role]

        entries.sort(key=lambda e: e.recorded_at, reverse=True)
        return entries[:limit]

    def _write_per_spec(self, project_id: str, spec_id: str, line: str) -> None:
        """Write an audit line to the per-spec audit log."""
        path = self._spec_audit_path(project_id, spec_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            logger.exception("Failed to write per-spec audit entry")

    def _spec_audit_path(self, project_id: str, spec_id: str) -> Path:
        """Return the per-spec audit log path."""
        return self._projects_dir / project_id / "specs" / spec_id / ".vizier" / AUDIT_FILENAME

    def _read_file(self, path: Path) -> list[AuditEntry]:
        """Read all audit entries from a JSONL file."""
        if not path.exists():
            return []
        entries: list[AuditEntry] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(AuditEntry.model_validate_json(line))
            except Exception:
                continue
        return entries

    def _truncate_result(self, result: dict[str, Any]) -> dict[str, Any]:
        """Truncate large string values in the result dict."""
        truncated: dict[str, Any] = {}
        for key, value in result.items():
            if isinstance(value, str) and len(value) > self._max_output_chars:
                truncated[key] = value[: self._max_output_chars] + f"... [truncated, {len(value)} chars total]"
            else:
                truncated[key] = value
        return truncated

    def _maybe_rotate(self) -> None:
        """Rotate the global audit log if it exceeds the size limit."""
        try:
            if not self.global_log_path.exists():
                return
            size = self.global_log_path.stat().st_size
        except OSError:
            return

        if size < self._max_size_bytes:
            return

        for i in range(self._max_files, 0, -1):
            src = self._audit_dir / f"{AUDIT_FILENAME}.{i}"
            if i == self._max_files:
                if src.exists():
                    src.unlink()
            else:
                dst = self._audit_dir / f"{AUDIT_FILENAME}.{i + 1}"
                if src.exists():
                    src.rename(dst)

        dest = self._audit_dir / f"{AUDIT_FILENAME}.1"
        try:
            self.global_log_path.rename(dest)
        except OSError:
            logger.exception("Failed to rotate audit log file")
