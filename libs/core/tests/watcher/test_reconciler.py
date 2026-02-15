"""Tests for reconciler: periodic disk scan to catch missed events."""

import pytest

from vizier.core.file_protocol.spec_io import create_spec, update_spec_status
from vizier.core.models.events import EventType, FileEvent
from vizier.core.models.spec import SpecStatus
from vizier.core.watcher.reconciler import Reconciler


@pytest.fixture
def project_root(tmp_path):
    (tmp_path / ".vizier" / "specs").mkdir(parents=True)
    return tmp_path


class TestReconciler:
    def test_first_scan_generates_created_events(self, project_root) -> None:
        create_spec(project_root, "001-first", "First")
        create_spec(project_root, "002-second", "Second")

        events: list[FileEvent] = []
        reconciler = Reconciler(project_root, callback=events.append)
        result = reconciler.reconcile()

        assert len(result) == 2
        assert all(e.event_type == EventType.CREATED for e in result)
        assert all(e.is_synthetic for e in result)

    def test_no_changes_no_events(self, project_root) -> None:
        create_spec(project_root, "001-test", "Test")

        events: list[FileEvent] = []
        reconciler = Reconciler(project_root, callback=events.append)
        reconciler.reconcile()
        events.clear()
        result = reconciler.reconcile()
        assert len(result) == 0

    def test_status_change_generates_modified(self, project_root) -> None:
        spec = create_spec(project_root, "001-test", "Test")
        assert spec.file_path is not None

        events: list[FileEvent] = []
        reconciler = Reconciler(project_root, callback=events.append)
        reconciler.reconcile()
        events.clear()

        update_spec_status(spec.file_path, SpecStatus.READY)
        result = reconciler.reconcile()
        assert len(result) == 1
        assert result[0].event_type == EventType.MODIFIED

    def test_deleted_spec_generates_deleted(self, project_root) -> None:
        create_spec(project_root, "001-test", "Test")

        events: list[FileEvent] = []
        reconciler = Reconciler(project_root, callback=events.append)
        reconciler.reconcile()
        events.clear()

        import shutil

        shutil.rmtree(project_root / ".vizier" / "specs" / "001-test")

        result = reconciler.reconcile()
        assert len(result) == 1
        assert result[0].event_type == EventType.DELETED
        assert result[0].is_synthetic

    def test_known_states_tracked(self, project_root) -> None:
        create_spec(project_root, "001-test", "Test")

        reconciler = Reconciler(project_root, callback=lambda e: None)
        reconciler.reconcile()
        assert "001-test" in reconciler.known_states
        assert reconciler.known_states["001-test"] == SpecStatus.DRAFT

    def test_new_spec_detected(self, project_root) -> None:
        create_spec(project_root, "001-first", "First")

        events: list[FileEvent] = []
        reconciler = Reconciler(project_root, callback=events.append)
        reconciler.reconcile()
        events.clear()

        create_spec(project_root, "002-second", "Second")
        result = reconciler.reconcile()
        created = [e for e in result if e.event_type == EventType.CREATED]
        assert len(created) == 1
