"""Graceful shutdown for Pasha: transitions active specs to INTERRUPTED.

When Pasha receives a shutdown signal, it transitions all IN_PROGRESS specs
to INTERRUPTED state so they can be recovered on restart.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def graceful_shutdown(project_root: str) -> list[str]:
    """Transition all IN_PROGRESS specs to INTERRUPTED.

    :param project_root: Project root directory.
    :returns: List of spec IDs that were interrupted.
    """
    interrupted: list[str] = []
    specs_dir = os.path.join(project_root, ".vizier", "specs")

    if not os.path.isdir(specs_dir):
        return interrupted

    for spec_id in os.listdir(specs_dir):
        state_path = os.path.join(specs_dir, spec_id, "state.json")
        if not os.path.isfile(state_path):
            continue

        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)

            if state.get("status") == "IN_PROGRESS":
                state["status"] = "INTERRUPTED"
                state["interrupted_at"] = datetime.now(UTC).isoformat()
                state["interrupted_reason"] = "Pasha shutdown"

                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)

                interrupted.append(spec_id)
                logger.info("Interrupted spec %s during shutdown", spec_id)

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to interrupt spec %s: %s", spec_id, e)

    return interrupted


def recover_interrupted(project_root: str) -> list[str]:
    """Find interrupted specs that need recovery on startup.

    :param project_root: Project root directory.
    :returns: List of spec IDs in INTERRUPTED state.
    """
    interrupted: list[str] = []
    specs_dir = os.path.join(project_root, ".vizier", "specs")

    if not os.path.isdir(specs_dir):
        return interrupted

    for spec_id in os.listdir(specs_dir):
        state_path = os.path.join(specs_dir, spec_id, "state.json")
        if not os.path.isfile(state_path):
            continue

        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            if state.get("status") == "INTERRUPTED":
                interrupted.append(spec_id)
        except (json.JSONDecodeError, OSError):
            continue

    return interrupted
