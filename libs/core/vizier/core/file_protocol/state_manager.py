"""State manager with file locking for state.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from filelock import FileLock

from vizier.core.models.state import ProjectState

if TYPE_CHECKING:
    from collections.abc import Callable


class StateManager:
    """Manages .vizier/state.json with file-level locking.

    :param project_root: Root directory of the project (contains .vizier/).
    """

    def __init__(self, project_root: str | Path) -> None:
        self._root = Path(project_root)
        self._state_path = self._root / ".vizier" / "state.json"
        self._lock_path = self._root / ".vizier" / "state.json.lock"

    @property
    def state_path(self) -> Path:
        return self._state_path

    def read_state(self) -> ProjectState:
        """Read current state from disk.

        :returns: Current ProjectState, or a default if file doesn't exist.
        """
        if not self._state_path.exists():
            return ProjectState(project=self._root.name)

        with FileLock(str(self._lock_path)):
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
            return ProjectState.model_validate(data)

    def write_state(self, state: ProjectState) -> None:
        """Write state to disk with locking.

        :param state: The state to persist.
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self._lock_path)):
            self._state_path.write_text(
                json.dumps(state.model_dump(mode="json"), indent=2, default=str),
                encoding="utf-8",
            )

    def update_state(self, updater: Callable[[ProjectState], ProjectState]) -> ProjectState:
        """Atomic read-modify-write with file locking.

        :param updater: Callback that receives current state and returns updated state.
        :returns: The updated state after writing.
        """
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self._lock_path)):
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                state = ProjectState.model_validate(data)
            else:
                state = ProjectState(project=self._root.name)

            updated = updater(state)
            self._state_path.write_text(
                json.dumps(updated.model_dump(mode="json"), indent=2, default=str),
                encoding="utf-8",
            )
            return updated
