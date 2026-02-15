"""Tests for spec models and state machine transitions."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from vizier.core.models.spec import VALID_TRANSITIONS, Spec, SpecComplexity, SpecFrontmatter, SpecStatus


class TestSpecStatus:
    def test_all_statuses_exist(self) -> None:
        expected = {"DRAFT", "READY", "IN_PROGRESS", "REVIEW", "DONE", "REJECTED", "STUCK", "DECOMPOSED", "INTERRUPTED"}
        assert {s.value for s in SpecStatus} == expected

    def test_status_is_str(self) -> None:
        assert str(SpecStatus.DRAFT) == "DRAFT"
        assert SpecStatus.DRAFT == "DRAFT"


class TestSpecComplexity:
    def test_all_complexities_exist(self) -> None:
        assert {c.value for c in SpecComplexity} == {"low", "medium", "high"}

    def test_complexity_is_str(self) -> None:
        assert str(SpecComplexity.LOW) == "low"


class TestValidTransitions:
    def test_all_statuses_have_transitions(self) -> None:
        for status in SpecStatus:
            assert status in VALID_TRANSITIONS, f"Missing transitions for {status}"

    def test_draft_transitions(self) -> None:
        assert set(VALID_TRANSITIONS[SpecStatus.DRAFT]) == {SpecStatus.READY, SpecStatus.DECOMPOSED}

    def test_ready_transitions(self) -> None:
        assert VALID_TRANSITIONS[SpecStatus.READY] == [SpecStatus.IN_PROGRESS]

    def test_in_progress_transitions(self) -> None:
        expected = {SpecStatus.REVIEW, SpecStatus.STUCK, SpecStatus.INTERRUPTED}
        assert set(VALID_TRANSITIONS[SpecStatus.IN_PROGRESS]) == expected

    def test_review_transitions(self) -> None:
        assert set(VALID_TRANSITIONS[SpecStatus.REVIEW]) == {SpecStatus.DONE, SpecStatus.REJECTED}

    def test_rejected_transitions(self) -> None:
        assert VALID_TRANSITIONS[SpecStatus.REJECTED] == [SpecStatus.IN_PROGRESS]

    def test_stuck_transitions(self) -> None:
        assert VALID_TRANSITIONS[SpecStatus.STUCK] == [SpecStatus.DECOMPOSED]

    def test_interrupted_transitions(self) -> None:
        assert VALID_TRANSITIONS[SpecStatus.INTERRUPTED] == [SpecStatus.READY]

    def test_terminal_states_have_no_transitions(self) -> None:
        assert VALID_TRANSITIONS[SpecStatus.DONE] == []
        assert VALID_TRANSITIONS[SpecStatus.DECOMPOSED] == []


class TestSpecFrontmatter:
    def test_minimal_creation(self) -> None:
        fm = SpecFrontmatter(id="001-test")
        assert fm.id == "001-test"
        assert fm.status == SpecStatus.DRAFT
        assert fm.priority == 1
        assert fm.complexity == SpecComplexity.MEDIUM
        assert fm.retries == 0
        assert fm.max_retries == 10
        assert fm.parent is None
        assert fm.plugin == "software"
        assert fm.assigned_to is None
        assert fm.requires_approval is False

    def test_full_creation(self) -> None:
        now = datetime(2026, 2, 15, 10, 0, 0)
        fm = SpecFrontmatter(
            id="001-auth/002-jwt",
            status=SpecStatus.IN_PROGRESS,
            priority=2,
            complexity=SpecComplexity.HIGH,
            retries=3,
            max_retries=5,
            parent="001-auth",
            plugin="software",
            created=now,
            updated=now,
            assigned_to="worker-1",
            requires_approval=True,
        )
        assert fm.id == "001-auth/002-jwt"
        assert fm.status == SpecStatus.IN_PROGRESS
        assert fm.priority == 2
        assert fm.complexity == SpecComplexity.HIGH
        assert fm.retries == 3
        assert fm.parent == "001-auth"
        assert fm.assigned_to == "worker-1"
        assert fm.requires_approval is True

    def test_priority_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SpecFrontmatter(id="001-test", priority=0)

    def test_retries_cannot_be_negative(self) -> None:
        with pytest.raises(ValidationError):
            SpecFrontmatter(id="001-test", retries=-1)

    def test_max_retries_must_be_at_least_one(self) -> None:
        with pytest.raises(ValidationError):
            SpecFrontmatter(id="001-test", max_retries=0)

    def test_status_from_string(self) -> None:
        fm = SpecFrontmatter(id="001-test", status="READY")  # type: ignore[arg-type]
        assert fm.status == SpecStatus.READY

    def test_complexity_from_string(self) -> None:
        fm = SpecFrontmatter(id="001-test", complexity="high")  # type: ignore[arg-type]
        assert fm.complexity == SpecComplexity.HIGH

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValidationError):
            SpecFrontmatter(id="001-test", status="INVALID")  # type: ignore[arg-type]

    def test_serialization_roundtrip(self) -> None:
        fm = SpecFrontmatter(id="001-test", status=SpecStatus.READY, complexity=SpecComplexity.LOW)
        data = fm.model_dump()
        restored = SpecFrontmatter.model_validate(data)
        assert restored == fm


class TestSpec:
    def test_creation_with_content(self) -> None:
        fm = SpecFrontmatter(id="001-test")
        spec = Spec(frontmatter=fm, content="# Test Spec\n\nSome content.")
        assert spec.frontmatter.id == "001-test"
        assert spec.content == "# Test Spec\n\nSome content."
        assert spec.file_path is None

    def test_creation_with_file_path(self) -> None:
        fm = SpecFrontmatter(id="001-test")
        spec = Spec(frontmatter=fm, content="", file_path="/path/to/spec.md")
        assert spec.file_path == "/path/to/spec.md"

    def test_default_empty_content(self) -> None:
        fm = SpecFrontmatter(id="001-test")
        spec = Spec(frontmatter=fm)
        assert spec.content == ""
