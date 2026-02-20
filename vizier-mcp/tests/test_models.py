"""Tests for spec models and state machine."""

from __future__ import annotations

import pytest

from vizier_mcp.models.spec import (
    VALID_TRANSITIONS,
    Spec,
    SpecCreateRequest,
    SpecFeedback,
    SpecMetadata,
    SpecStatus,
    SpecSummary,
    SpecTransitionRequest,
    SpecUpdateRequest,
    is_valid_transition,
)


class TestSpecStatus:
    """Tests for the SpecStatus enum."""

    def test_all_eight_states_exist(self) -> None:
        expected = {"DRAFT", "READY", "IN_PROGRESS", "REVIEW", "REJECTED", "DONE", "STUCK", "INTERRUPTED"}
        actual = {s.value for s in SpecStatus}
        assert actual == expected

    def test_status_from_string(self) -> None:
        assert SpecStatus("DRAFT") == SpecStatus.DRAFT
        assert SpecStatus("IN_PROGRESS") == SpecStatus.IN_PROGRESS

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError):
            SpecStatus("INVALID")


class TestValidTransitions:
    """Tests for the v1 state machine transitions."""

    def test_draft_to_ready(self) -> None:
        assert is_valid_transition(SpecStatus.DRAFT, SpecStatus.READY)

    def test_draft_only_goes_to_ready(self) -> None:
        for target in SpecStatus:
            if target == SpecStatus.READY:
                assert is_valid_transition(SpecStatus.DRAFT, target)
            else:
                assert not is_valid_transition(SpecStatus.DRAFT, target)

    def test_ready_to_in_progress(self) -> None:
        assert is_valid_transition(SpecStatus.READY, SpecStatus.IN_PROGRESS)

    def test_ready_to_stuck(self) -> None:
        assert is_valid_transition(SpecStatus.READY, SpecStatus.STUCK)

    def test_in_progress_to_review(self) -> None:
        assert is_valid_transition(SpecStatus.IN_PROGRESS, SpecStatus.REVIEW)

    def test_in_progress_to_interrupted(self) -> None:
        assert is_valid_transition(SpecStatus.IN_PROGRESS, SpecStatus.INTERRUPTED)

    def test_review_to_done(self) -> None:
        assert is_valid_transition(SpecStatus.REVIEW, SpecStatus.DONE)

    def test_review_to_rejected(self) -> None:
        assert is_valid_transition(SpecStatus.REVIEW, SpecStatus.REJECTED)

    def test_rejected_to_ready(self) -> None:
        assert is_valid_transition(SpecStatus.REJECTED, SpecStatus.READY)

    def test_rejected_to_stuck(self) -> None:
        assert is_valid_transition(SpecStatus.REJECTED, SpecStatus.STUCK)

    def test_interrupted_to_ready(self) -> None:
        assert is_valid_transition(SpecStatus.INTERRUPTED, SpecStatus.READY)

    def test_done_is_terminal(self) -> None:
        for target in SpecStatus:
            assert not is_valid_transition(SpecStatus.DONE, target)

    def test_stuck_is_terminal(self) -> None:
        for target in SpecStatus:
            assert not is_valid_transition(SpecStatus.STUCK, target)

    def test_invalid_backward_transitions(self) -> None:
        assert not is_valid_transition(SpecStatus.READY, SpecStatus.DRAFT)
        assert not is_valid_transition(SpecStatus.REVIEW, SpecStatus.IN_PROGRESS)
        assert not is_valid_transition(SpecStatus.DONE, SpecStatus.REVIEW)

    def test_all_states_have_transition_entry(self) -> None:
        for status in SpecStatus:
            assert status in VALID_TRANSITIONS


class TestSpecMetadata:
    """Tests for the SpecMetadata model."""

    def test_defaults(self) -> None:
        meta = SpecMetadata(spec_id="001-test", project_id="proj", title="Test")
        assert meta.status == SpecStatus.DRAFT
        assert meta.complexity == "MEDIUM"
        assert meta.retry_count == 0
        assert meta.assigned_agent is None
        assert meta.claimed_at is None
        assert meta.depends_on == []

    def test_serialization_roundtrip(self) -> None:
        meta = SpecMetadata(spec_id="001-test", project_id="proj", title="Test")
        data = meta.model_dump(mode="json")
        restored = SpecMetadata(**data)
        assert restored.spec_id == meta.spec_id
        assert restored.status == meta.status


class TestSpec:
    """Tests for the Spec model."""

    def test_create_with_body(self) -> None:
        meta = SpecMetadata(spec_id="001-test", project_id="proj", title="Test")
        spec = Spec(metadata=meta, body="Do the thing", artifacts=["src/foo.py"], criteria=["Tests pass"])
        assert spec.body == "Do the thing"
        assert spec.artifacts == ["src/foo.py"]
        assert spec.criteria == ["Tests pass"]


class TestSpecSummary:
    """Tests for the SpecSummary model."""

    def test_from_metadata(self) -> None:
        summary = SpecSummary(
            spec_id="001-test",
            project_id="proj",
            title="Test",
            status=SpecStatus.DRAFT,
            complexity="MEDIUM",
            retry_count=0,
        )
        assert summary.assigned_agent is None


class TestSpecFeedback:
    """Tests for the SpecFeedback model."""

    def test_defaults(self) -> None:
        fb = SpecFeedback(spec_id="001-test", verdict="REJECT", feedback="Missing tests")
        assert fb.reviewer == "quality_gate"
        assert fb.created_at is not None


class TestSpecRequests:
    """Tests for request models."""

    def test_create_request_defaults(self) -> None:
        req = SpecCreateRequest(project_id="proj", title="Test", description="Do it")
        assert req.complexity == "MEDIUM"
        assert req.artifacts == []
        assert req.criteria == []
        assert req.depends_on == []

    def test_transition_request(self) -> None:
        req = SpecTransitionRequest(spec_id="001-test", new_status=SpecStatus.READY, agent_role="pasha")
        assert req.reason == ""

    def test_update_request(self) -> None:
        req = SpecUpdateRequest(spec_id="001-test", fields={"retry_count": 3})
        assert req.fields["retry_count"] == 3
