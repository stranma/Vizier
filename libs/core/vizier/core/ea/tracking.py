"""Commitment and relationship tracking for EA."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml

from vizier.core.ea.models import Commitment, CommitmentStatus, Relationship


class CommitmentTracker:
    """CRUD operations for Sultan's commitments.

    :param data_dir: Path to ea/commitments/ directory.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(self, commitment: Commitment) -> Path:
        """Write a commitment to disk.

        :param commitment: The commitment to persist.
        :returns: Path to the written file.
        """
        path = self._dir / f"{commitment.id}.yaml"
        self._atomic_write(path, commitment)
        return path

    def read(self, commitment_id: str) -> Commitment | None:
        """Read a commitment by ID.

        :param commitment_id: The commitment ID.
        :returns: The commitment or None if not found.
        """
        path = self._dir / f"{commitment_id}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Commitment(**data) if data else None

    def update(self, commitment: Commitment) -> Path:
        """Update an existing commitment on disk.

        :param commitment: The commitment with updated fields.
        :returns: Path to the written file.
        """
        commitment.updated = datetime.utcnow()
        return self.create(commitment)

    def delete(self, commitment_id: str) -> bool:
        """Delete a commitment file.

        :param commitment_id: The commitment ID to delete.
        :returns: True if deleted, False if not found.
        """
        path = self._dir / f"{commitment_id}.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_all(self) -> list[Commitment]:
        """List all commitments from disk.

        :returns: List of all commitments.
        """
        commitments: list[Commitment] = []
        for f in sorted(self._dir.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data:
                commitments.append(Commitment(**data))
        return commitments

    def list_active(self) -> list[Commitment]:
        """List commitments that are pending or in progress.

        :returns: Active commitments.
        """
        return [c for c in self.list_all() if c.status in (CommitmentStatus.PENDING, CommitmentStatus.IN_PROGRESS)]

    def list_overdue(self) -> list[Commitment]:
        """List commitments past their deadline.

        :returns: Overdue commitments.
        """
        now = datetime.utcnow()
        return [c for c in self.list_active() if c.deadline is not None and c.deadline < now]

    def _atomic_write(self, path: Path, commitment: Commitment) -> None:
        """Write commitment using atomic write-then-rename pattern."""
        tmp_path = path.with_suffix(".yaml.tmp")
        data = commitment.model_dump(mode="json")
        tmp_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        os.replace(str(tmp_path), str(path))


class RelationshipTracker:
    """CRUD operations for Sultan's contact relationships.

    :param data_dir: Path to ea/relationships/ directory.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def create(self, relationship: Relationship) -> Path:
        """Write a relationship to disk.

        :param relationship: The relationship to persist.
        :returns: Path to the written file.
        """
        path = self._dir / f"{relationship.id}.yaml"
        self._atomic_write(path, relationship)
        return path

    def read(self, relationship_id: str) -> Relationship | None:
        """Read a relationship by ID.

        :param relationship_id: The relationship ID.
        :returns: The relationship or None if not found.
        """
        path = self._dir / f"{relationship_id}.yaml"
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return Relationship(**data) if data else None

    def update(self, relationship: Relationship) -> Path:
        """Update an existing relationship on disk.

        :param relationship: The relationship with updated fields.
        :returns: Path to the written file.
        """
        relationship.updated = datetime.utcnow()
        return self.create(relationship)

    def delete(self, relationship_id: str) -> bool:
        """Delete a relationship file.

        :param relationship_id: The relationship ID to delete.
        :returns: True if deleted, False if not found.
        """
        path = self._dir / f"{relationship_id}.yaml"
        if path.exists():
            path.unlink()
            return True
        return False

    def list_all(self) -> list[Relationship]:
        """List all relationships from disk.

        :returns: List of all relationships.
        """
        relationships: list[Relationship] = []
        for f in sorted(self._dir.glob("*.yaml")):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data:
                relationships.append(Relationship(**data))
        return relationships

    def find_by_name(self, name: str) -> Relationship | None:
        """Find a relationship by contact name (case-insensitive).

        :param name: The contact name to search for.
        :returns: The matching relationship or None.
        """
        name_lower = name.lower()
        for rel in self.list_all():
            if rel.name.lower() == name_lower:
                return rel
        return None

    def with_overdue_followups(self, days_threshold: int = 7) -> list[Relationship]:
        """Find relationships with last contact older than threshold.

        :param days_threshold: Number of days before a follow-up is considered overdue.
        :returns: Relationships needing follow-up.
        """
        now = datetime.utcnow()
        overdue: list[Relationship] = []
        for rel in self.list_all():
            if rel.last_contact is not None:
                days_since = (now - rel.last_contact).days
                if days_since >= days_threshold:
                    overdue.append(rel)
        return overdue

    def _atomic_write(self, path: Path, relationship: Relationship) -> None:
        """Write relationship using atomic write-then-rename pattern."""
        tmp_path = path.with_suffix(".yaml.tmp")
        data = relationship.model_dump(mode="json")
        tmp_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        os.replace(str(tmp_path), str(path))
