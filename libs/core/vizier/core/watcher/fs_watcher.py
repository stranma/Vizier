"""Filesystem watcher: watchdog wrapper for spec file change detection."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from vizier.core.models.events import EventType, FileEvent

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class _SpecEventHandler(FileSystemEventHandler):
    """Translates watchdog events into FileEvent objects."""

    def __init__(self, callback: Callable[[FileEvent], None]) -> None:
        super().__init__()
        self._callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".md"):
            self._dispatch(EventType.CREATED, str(event.src_path))

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".md"):
            self._dispatch(EventType.MODIFIED, str(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".md"):
            self._dispatch(EventType.DELETED, str(event.src_path))

    def _dispatch(self, event_type: EventType, path: str) -> None:
        file_event = FileEvent(
            event_type=event_type,
            path=path,
            timestamp=datetime.utcnow(),
            is_synthetic=False,
        )
        self._callback(file_event)


class FileSystemWatcher:
    """Watches a directory for spec file changes using watchdog.

    :param watch_path: Directory to watch (e.g. .vizier/specs/).
    :param callback: Function called for each FileEvent.
    :param recursive: Whether to watch subdirectories.
    """

    def __init__(
        self,
        watch_path: str | Path,
        callback: Callable[[FileEvent], None],
        recursive: bool = True,
    ) -> None:
        self._path = str(watch_path)
        self._callback = callback
        self._recursive = recursive
        self._observer: Any = None
        self._handler = _SpecEventHandler(callback)

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def start(self) -> None:
        """Start watching for filesystem events."""
        if self._observer is not None:
            return
        observer = Observer()
        observer.schedule(self._handler, self._path, recursive=self._recursive)
        observer.daemon = True
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        """Stop watching for filesystem events."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
