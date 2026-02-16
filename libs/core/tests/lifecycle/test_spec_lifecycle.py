"""Tests for spec lifecycle management."""

from __future__ import annotations

from typing import Any

import pytest

from vizier.core.file_protocol.spec_io import create_spec, read_spec, update_spec_status
from vizier.core.lifecycle.retry import RetryAction
from vizier.core.lifecycle.spec_lifecycle import SpecLifecycle
from vizier.core.models.spec import SpecStatus


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier" / "specs"
    vizier_dir.mkdir(parents=True)
    return str(tmp_path)


def _make_rejected_spec(project_dir: str, spec_id: str, retries: int = 0) -> str:
    spec = create_spec(
        project_dir,
        spec_id,
        "test task",
        {"status": "READY", "priority": 1, "plugin": "test-stub"},
    )
    update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS)
    update_spec_status(spec.file_path or "", SpecStatus.REVIEW)
    update_spec_status(
        spec.file_path or "",
        SpecStatus.REJECTED,
        extra_updates={"retries": retries},
    )
    return spec.file_path or ""


class TestHandleRejection:
    def test_increments_retries(self, project_dir: str) -> None:
        spec_path = _make_rejected_spec(project_dir, "001-retry")
        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)

        assert action == RetryAction.CONTINUE
        spec = read_spec(spec_path)
        assert spec.frontmatter.retries == 1
        assert spec.frontmatter.status == SpecStatus.IN_PROGRESS

    def test_bump_model_at_retry_3(self, project_dir: str) -> None:
        spec_path = _make_rejected_spec(project_dir, "001-bump", retries=2)
        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)

        assert action == RetryAction.BUMP_MODEL
        spec = read_spec(spec_path)
        assert spec.frontmatter.retries == 3

    def test_alert_pasha_at_retry_5(self, project_dir: str) -> None:
        spec_path = _make_rejected_spec(project_dir, "001-pasha", retries=4)
        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)

        assert action == RetryAction.ALERT_PASHA

    def test_re_decompose_at_retry_7(self, project_dir: str) -> None:
        spec_path = _make_rejected_spec(project_dir, "001-decompose", retries=6)
        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)

        assert action == RetryAction.RE_DECOMPOSE

    def test_stuck_at_retry_10(self, project_dir: str) -> None:
        spec_path = _make_rejected_spec(project_dir, "001-stuck", retries=9)
        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)

        assert action == RetryAction.STUCK
        spec = read_spec(spec_path)
        assert spec.frontmatter.status == SpecStatus.STUCK

    def test_non_rejected_raises(self, project_dir: str) -> None:
        spec = create_spec(project_dir, "001-ready", "test", {"status": "READY"})
        lifecycle = SpecLifecycle()
        with pytest.raises(ValueError, match="not REJECTED"):
            lifecycle.handle_rejection(spec.file_path or "")


class TestInterruptedHandling:
    def test_interrupt_active_specs(self, project_dir: str) -> None:
        spec1 = create_spec(project_dir, "001-active", "task 1", {"status": "READY"})
        update_spec_status(spec1.file_path or "", SpecStatus.IN_PROGRESS, {"assigned_to": "w1"})

        spec2 = create_spec(project_dir, "002-active", "task 2", {"status": "READY"})
        update_spec_status(spec2.file_path or "", SpecStatus.IN_PROGRESS, {"assigned_to": "w2"})

        spec3 = create_spec(project_dir, "003-ready", "task 3", {"status": "READY"})

        interrupted = SpecLifecycle.interrupt_active_specs(project_dir)

        assert len(interrupted) == 2
        assert "001-active" in interrupted
        assert "002-active" in interrupted

        s1 = read_spec(spec1.file_path or "")
        assert s1.frontmatter.status == SpecStatus.INTERRUPTED
        assert s1.frontmatter.assigned_to is None

        s3 = read_spec(spec3.file_path or "")
        assert s3.frontmatter.status == SpecStatus.READY

    def test_requeue_interrupted_specs(self, project_dir: str) -> None:
        spec1 = create_spec(project_dir, "001-int", "task 1", {"status": "READY"})
        update_spec_status(spec1.file_path or "", SpecStatus.IN_PROGRESS)
        update_spec_status(spec1.file_path or "", SpecStatus.INTERRUPTED)

        spec2 = create_spec(project_dir, "002-int", "task 2", {"status": "READY"})
        update_spec_status(spec2.file_path or "", SpecStatus.IN_PROGRESS)
        update_spec_status(spec2.file_path or "", SpecStatus.INTERRUPTED)

        re_queued = SpecLifecycle.handle_interrupted_specs(project_dir)

        assert len(re_queued) == 2

        s1 = read_spec(spec1.file_path or "")
        assert s1.frontmatter.status == SpecStatus.READY
        assert s1.frontmatter.assigned_to is None

    def test_no_interrupted_specs(self, project_dir: str) -> None:
        create_spec(project_dir, "001-ready", "task", {"status": "READY"})
        re_queued = SpecLifecycle.handle_interrupted_specs(project_dir)
        assert re_queued == []
