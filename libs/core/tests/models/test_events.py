"""Tests for filesystem event models."""

from vizier.core.models.events import EventType, FileEvent


class TestEventType:
    def test_all_types_exist(self) -> None:
        assert {e.value for e in EventType} == {"created", "modified", "deleted"}


class TestFileEvent:
    def test_creation(self) -> None:
        event = FileEvent(event_type=EventType.CREATED, path="/path/to/spec.md")
        assert event.event_type == EventType.CREATED
        assert event.path == "/path/to/spec.md"
        assert event.is_synthetic is False

    def test_synthetic_event(self) -> None:
        event = FileEvent(event_type=EventType.MODIFIED, path="/path/to/spec.md", is_synthetic=True)
        assert event.is_synthetic is True

    def test_from_string(self) -> None:
        event = FileEvent(event_type="created", path="/path")  # type: ignore[arg-type]
        assert event.event_type == EventType.CREATED
