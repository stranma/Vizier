"""Tests for commitment and relationship tracking."""

from datetime import datetime, timedelta
from pathlib import Path

from vizier.core.ea.models import Commitment, CommitmentStatus, Relationship
from vizier.core.ea.tracking import CommitmentTracker, RelationshipTracker


class TestCommitmentTracker:
    def test_create_and_read(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        commitment = Commitment(id="c1", description="Deliver report", promised_to="Board")
        tracker.create(commitment)

        result = tracker.read("c1")
        assert result is not None
        assert result.id == "c1"
        assert result.description == "Deliver report"

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        assert tracker.read("nonexistent") is None

    def test_update(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        commitment = Commitment(id="c1", description="Deliver report", promised_to="Board")
        tracker.create(commitment)

        commitment.status = CommitmentStatus.IN_PROGRESS
        tracker.update(commitment)

        result = tracker.read("c1")
        assert result is not None
        assert result.status == CommitmentStatus.IN_PROGRESS

    def test_delete(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        commitment = Commitment(id="c1", description="Test", promised_to="Someone")
        tracker.create(commitment)
        assert tracker.delete("c1") is True
        assert tracker.read("c1") is None

    def test_delete_nonexistent(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        assert tracker.delete("nonexistent") is False

    def test_list_all(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        tracker.create(Commitment(id="c1", description="First", promised_to="A"))
        tracker.create(Commitment(id="c2", description="Second", promised_to="B"))
        all_commitments = tracker.list_all()
        assert len(all_commitments) == 2

    def test_list_active(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        tracker.create(Commitment(id="c1", description="Active", promised_to="A", status=CommitmentStatus.PENDING))
        tracker.create(Commitment(id="c2", description="Done", promised_to="B", status=CommitmentStatus.COMPLETED))
        active = tracker.list_active()
        assert len(active) == 1
        assert active[0].id == "c1"

    def test_list_overdue(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        past = datetime.utcnow() - timedelta(days=5)
        future = datetime.utcnow() + timedelta(days=5)
        tracker.create(Commitment(id="c1", description="Overdue", promised_to="A", deadline=past))
        tracker.create(Commitment(id="c2", description="Not due", promised_to="B", deadline=future))
        overdue = tracker.list_overdue()
        assert len(overdue) == 1
        assert overdue[0].id == "c1"

    def test_atomic_write_no_tmp_files(self, tmp_path: Path) -> None:
        tracker = CommitmentTracker(tmp_path / "commitments")
        tracker.create(Commitment(id="c1", description="Test", promised_to="Someone"))
        tmp_files = list((tmp_path / "commitments").glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_creates_directory(self, tmp_path: Path) -> None:
        dir_path = tmp_path / "nested" / "commitments"
        tracker = CommitmentTracker(dir_path)
        assert dir_path.exists()
        tracker.create(Commitment(id="c1", description="Test", promised_to="Someone"))
        assert tracker.read("c1") is not None


class TestRelationshipTracker:
    def test_create_and_read(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        rel = Relationship(id="r1", name="Jan Novak", role="Partner")
        tracker.create(rel)

        result = tracker.read("r1")
        assert result is not None
        assert result.name == "Jan Novak"

    def test_read_nonexistent(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        assert tracker.read("nonexistent") is None

    def test_update(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        rel = Relationship(id="r1", name="Jan Novak")
        tracker.create(rel)

        rel.role = "CEO"
        tracker.update(rel)

        result = tracker.read("r1")
        assert result is not None
        assert result.role == "CEO"

    def test_delete(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        tracker.create(Relationship(id="r1", name="Jan Novak"))
        assert tracker.delete("r1") is True
        assert tracker.read("r1") is None

    def test_list_all(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        tracker.create(Relationship(id="r1", name="Jan Novak"))
        tracker.create(Relationship(id="r2", name="Lisa Smith"))
        assert len(tracker.list_all()) == 2

    def test_find_by_name(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        tracker.create(Relationship(id="r1", name="Jan Novak"))
        tracker.create(Relationship(id="r2", name="Lisa Smith"))

        result = tracker.find_by_name("jan novak")
        assert result is not None
        assert result.id == "r1"

    def test_find_by_name_not_found(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        assert tracker.find_by_name("Unknown") is None

    def test_overdue_followups(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        old_contact = datetime.utcnow() - timedelta(days=10)
        recent_contact = datetime.utcnow() - timedelta(days=2)
        tracker.create(Relationship(id="r1", name="Jan", last_contact=old_contact))
        tracker.create(Relationship(id="r2", name="Lisa", last_contact=recent_contact))

        overdue = tracker.with_overdue_followups(days_threshold=7)
        assert len(overdue) == 1
        assert overdue[0].id == "r1"

    def test_atomic_write_no_tmp_files(self, tmp_path: Path) -> None:
        tracker = RelationshipTracker(tmp_path / "relationships")
        tracker.create(Relationship(id="r1", name="Jan Novak"))
        tmp_files = list((tmp_path / "relationships").glob("*.tmp"))
        assert len(tmp_files) == 0
