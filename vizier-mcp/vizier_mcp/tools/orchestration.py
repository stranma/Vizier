"""Orchestration tools: orch_write_ping (D77).

Provides supervisor ping functionality for inner agents to escalate
to their Pasha. Phase B tools (orch_scan_specs, orch_check_ready,
orch_assign_worker) are stubs -- build when multi-spec projects start.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from vizier_mcp.models.orchestration import PingMessage, PingUrgency

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)

_VALID_URGENCIES = {u.value for u in PingUrgency}


def _check_containment(base: Path, candidate: Path) -> bool:
    """Verify that candidate path is contained within base directory."""
    return str(candidate.resolve()).startswith(str(base.resolve()))


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically using write-then-rename (D40).

    :param path: Target file path.
    :param content: Content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def orch_write_ping(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    urgency: str,
    message: str,
) -> dict:
    """Write a ping from an inner agent to its Pasha (D77).

    Writes a JSON file to {spec_dir}/pings/{timestamp}-{urgency}.json.
    Uses atomic write (write-then-rename) per D40.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec context for the ping.
    :param urgency: One of QUESTION, BLOCKER, IMPOSSIBLE (D77).
    :param message: Description of the issue.
    :return: {"written": True, "path": str} or {"error": str}.
    """
    if urgency not in _VALID_URGENCIES:
        return {"error": f"Invalid urgency '{urgency}'. Must be one of: {', '.join(sorted(_VALID_URGENCIES))}"}

    assert config.projects_dir is not None
    project_dir = config.projects_dir / project_id
    if not _check_containment(config.projects_dir, project_dir):
        return {"error": f"Invalid project ID: '{project_id}'"}
    if not project_dir.is_dir():
        return {"error": f"Project '{project_id}' not found"}

    spec_dir = project_dir / "specs" / spec_id
    if not _check_containment(project_dir, spec_dir):
        return {"error": f"Invalid spec ID: '{spec_id}'"}
    if not spec_dir.is_dir():
        return {"error": f"Spec '{spec_id}' not found in project '{project_id}'"}

    pings_dir = spec_dir / "pings"
    pings_dir.mkdir(exist_ok=True)

    now = datetime.now(UTC)
    ping = PingMessage(
        spec_id=spec_id,
        urgency=PingUrgency(urgency),
        message=message,
        created_at=now,
    )

    timestamp = now.strftime("%Y%m%dT%H%M%S%f")
    filename = f"{timestamp}-{urgency}.json"
    ping_path = pings_dir / filename

    _atomic_write(ping_path, json.dumps(ping.model_dump(mode="json"), indent=2))

    return {"written": True, "path": str(ping_path)}
