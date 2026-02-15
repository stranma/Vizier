"""Tests for filesystem watcher."""

import time

from vizier.core.models.events import EventType, FileEvent
from vizier.core.watcher.fs_watcher import FileSystemWatcher


class TestFileSystemWatcher:
    def test_start_stop(self, tmp_path) -> None:
        events: list[FileEvent] = []
        watcher = FileSystemWatcher(tmp_path, callback=events.append)
        assert not watcher.is_running
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_detects_file_creation(self, tmp_path) -> None:
        events: list[FileEvent] = []
        watcher = FileSystemWatcher(tmp_path, callback=events.append)
        watcher.start()
        try:
            time.sleep(0.5)
            (tmp_path / "test.md").write_text("content", encoding="utf-8")
            time.sleep(1.0)
        finally:
            watcher.stop()
        md_events = [e for e in events if "test.md" in e.path]
        assert len(md_events) > 0

    def test_ignores_non_md_files(self, tmp_path) -> None:
        events: list[FileEvent] = []
        watcher = FileSystemWatcher(tmp_path, callback=events.append)
        watcher.start()
        try:
            time.sleep(0.5)
            (tmp_path / "test.txt").write_text("content", encoding="utf-8")
            time.sleep(1.0)
        finally:
            watcher.stop()
        assert len(events) == 0

    def test_detects_modification(self, tmp_path) -> None:
        (tmp_path / "test.md").write_text("original", encoding="utf-8")
        events: list[FileEvent] = []
        watcher = FileSystemWatcher(tmp_path, callback=events.append)
        watcher.start()
        try:
            time.sleep(0.5)
            (tmp_path / "test.md").write_text("modified", encoding="utf-8")
            time.sleep(1.0)
        finally:
            watcher.stop()
        modified_events = [e for e in events if e.event_type == EventType.MODIFIED]
        assert len(modified_events) > 0

    def test_double_start_is_safe(self, tmp_path) -> None:
        watcher = FileSystemWatcher(tmp_path, callback=lambda e: None)
        watcher.start()
        watcher.start()
        assert watcher.is_running
        watcher.stop()
