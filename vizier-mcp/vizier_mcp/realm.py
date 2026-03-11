"""Realm state manager.

Manages the persistent realm.json file that tracks all projects
and their container states. Provides CRUD operations for projects
and atomic state persistence.
"""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from pathlib import Path
from typing import Any

from vizier_mcp.models.realm import ContainerStatus, Project, ProjectType, RealmState

logger = logging.getLogger(__name__)

REALM_FILENAME = "realm.json"


class RealmManager:
    """Manages realm state with atomic file persistence.

    :param vizier_root: Root directory for all Vizier data.
    """

    def __init__(self, vizier_root: Path) -> None:
        self._vizier_root = vizier_root
        self._realm_path = vizier_root / REALM_FILENAME
        self._lock = threading.Lock()
        vizier_root.mkdir(parents=True, exist_ok=True)

    @property
    def realm_path(self) -> Path:
        """Path to the realm.json file."""
        return self._realm_path

    @property
    def repos_dir(self) -> Path:
        """Directory where project repos are stored."""
        return self._vizier_root / "repos"

    def load(self) -> RealmState:
        """Load realm state from disk. Returns empty state if file doesn't exist."""
        if not self._realm_path.exists():
            return RealmState()
        try:
            data = json.loads(self._realm_path.read_text(encoding="utf-8"))
            return RealmState.model_validate(data)
        except Exception:
            logger.exception("Failed to load realm.json, returning empty state")
            return RealmState()

    def _save_unlocked(self, state: RealmState) -> None:
        """Atomically save realm state to disk. Caller must hold ``_lock``."""
        data = state.model_dump(mode="json")
        content = json.dumps(data, indent=2) + "\n"
        fd, tmp_path = tempfile.mkstemp(dir=self._vizier_root, suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_path).replace(self._realm_path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def save(self, state: RealmState) -> None:
        """Atomically save realm state to disk (acquires lock)."""
        with self._lock:
            self._save_unlocked(state)

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID, or None if not found."""
        state = self.load()
        return state.projects.get(project_id)

    def list_projects(self, type_filter: str | None = None) -> list[dict[str, Any]]:
        """List all projects, optionally filtered by type."""
        state = self.load()
        projects = list(state.projects.values())
        if type_filter:
            try:
                pt = ProjectType(type_filter)
                projects = [p for p in projects if p.type == pt]
            except ValueError:
                pass
        return [p.to_summary() for p in projects]

    def add_project(self, project: Project) -> None:
        """Add a project to the realm. Raises ValueError if ID exists."""
        with self._lock:
            state = self.load()
            if project.id in state.projects:
                msg = f"Project already exists: {project.id}"
                raise ValueError(msg)
            state.projects[project.id] = project
            self._save_unlocked(state)

    def update_project(self, project_id: str, **updates: Any) -> Project:
        """Update project fields. Raises KeyError if not found."""
        with self._lock:
            state = self.load()
            if project_id not in state.projects:
                msg = f"Project not found: {project_id}"
                raise KeyError(msg)
            project = state.projects[project_id]
            for key, value in updates.items():
                if hasattr(project, key):
                    setattr(project, key, value)
            self._save_unlocked(state)
        return project

    def update_container_status(
        self, project_id: str, status: ContainerStatus, container_name: str | None = None
    ) -> None:
        """Update a project's container status and optionally its container name."""
        with self._lock:
            state = self.load()
            if project_id not in state.projects:
                msg = f"Project not found: {project_id}"
                raise KeyError(msg)
            project = state.projects[project_id]
            project.container_status = status
            if container_name is not None:
                project.container_name = container_name
            self._save_unlocked(state)
