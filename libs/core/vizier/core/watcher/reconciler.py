"""Reconciler: periodic disk scan to catch missed events (D22)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from vizier.core.file_protocol.spec_io import list_specs
from vizier.core.models.events import EventType, FileEvent

if TYPE_CHECKING:
    from collections.abc import Callable

    from vizier.core.models.spec import SpecStatus


class Reconciler:
    """Scans specs on disk and generates synthetic events for missed changes.

    Events are optimization; disk is truth (D22). The reconciler ensures
    that any spec changes missed by the filesystem watcher are detected
    on the next reconciliation cycle.

    :param project_root: Root directory of the project.
    :param callback: Function called for each synthetic FileEvent.
    """

    def __init__(
        self,
        project_root: str | Path,
        callback: Callable[[FileEvent], None],
    ) -> None:
        self._root = Path(project_root)
        self._callback = callback
        self._known_states: dict[str, SpecStatus] = {}

    def reconcile(self) -> list[FileEvent]:
        """Scan all specs and generate synthetic events for changes.

        :returns: List of synthetic FileEvents generated.
        """
        events: list[FileEvent] = []
        current_specs = list_specs(self._root)
        current_ids = {spec.frontmatter.id for spec in current_specs}

        for spec in current_specs:
            spec_id = spec.frontmatter.id
            current_status = spec.frontmatter.status

            if spec_id not in self._known_states:
                event = FileEvent(
                    event_type=EventType.CREATED,
                    path=spec.file_path or "",
                    timestamp=datetime.utcnow(),
                    is_synthetic=True,
                )
                events.append(event)
                self._callback(event)
            elif self._known_states[spec_id] != current_status:
                event = FileEvent(
                    event_type=EventType.MODIFIED,
                    path=spec.file_path or "",
                    timestamp=datetime.utcnow(),
                    is_synthetic=True,
                )
                events.append(event)
                self._callback(event)

            self._known_states[spec_id] = current_status

        for spec_id in list(self._known_states.keys()):
            if spec_id not in current_ids:
                event = FileEvent(
                    event_type=EventType.DELETED,
                    path=f"{self._root}/.vizier/specs/{spec_id}",
                    timestamp=datetime.utcnow(),
                    is_synthetic=True,
                )
                events.append(event)
                self._callback(event)
                del self._known_states[spec_id]

        return events

    @property
    def known_states(self) -> dict[str, SpecStatus]:
        """Current known spec states (for testing/inspection)."""
        return dict(self._known_states)
