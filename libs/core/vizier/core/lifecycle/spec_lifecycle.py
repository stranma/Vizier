"""Spec lifecycle: coordinates Worker -> QualityGate -> retry/done flow."""

from __future__ import annotations

import logging

from vizier.core.file_protocol.spec_io import list_specs, read_spec, update_spec_status
from vizier.core.lifecycle.retry import GraduatedRetry, RetryAction
from vizier.core.models.spec import SpecStatus

logger = logging.getLogger(__name__)


class SpecLifecycle:
    """Manages spec state transitions and the Worker -> QualityGate pipeline.

    This class coordinates the inner loop:
    1. Pick READY spec
    2. Transition to IN_PROGRESS (Worker claims)
    3. Worker completes -> REVIEW
    4. Quality Gate evaluates -> DONE or REJECTED
    5. If REJECTED: increment retries, apply graduated retry logic
    6. If retries exhausted: STUCK

    :param graduated_retry: Retry logic evaluator.
    """

    def __init__(self, graduated_retry: GraduatedRetry | None = None) -> None:
        self._retry = graduated_retry or GraduatedRetry()

    @property
    def retry_logic(self) -> GraduatedRetry:
        return self._retry

    def handle_rejection(self, spec_path: str) -> RetryAction:
        """Handle a REJECTED spec: increment retries and evaluate retry action.

        :param spec_path: Path to the spec file.
        :returns: The retry action to take.
        :raises ValueError: If spec is not in REJECTED status.
        """
        spec = read_spec(spec_path)
        if spec.frontmatter.status != SpecStatus.REJECTED:
            raise ValueError(f"Spec is not REJECTED: {spec.frontmatter.status}")

        new_retries = spec.frontmatter.retries + 1
        action = self._retry.evaluate(new_retries)

        if action == RetryAction.STUCK:
            update_spec_status(
                spec_path,
                SpecStatus.IN_PROGRESS,
                extra_updates={"retries": new_retries},
            )
            update_spec_status(spec_path, SpecStatus.STUCK)
            return action

        update_spec_status(
            spec_path,
            SpecStatus.IN_PROGRESS,
            extra_updates={"retries": new_retries, "assigned_to": None},
        )

        return action

    @staticmethod
    def handle_interrupted_specs(project_root: str) -> list[str]:
        """Re-queue INTERRUPTED specs as READY on daemon restart.

        :param project_root: Root directory of the project.
        :returns: List of spec IDs that were re-queued.
        """
        interrupted = list_specs(project_root, status_filter=SpecStatus.INTERRUPTED)
        re_queued: list[str] = []

        for spec in interrupted:
            if spec.file_path:
                update_spec_status(
                    spec.file_path,
                    SpecStatus.READY,
                    extra_updates={"assigned_to": None},
                )
                re_queued.append(spec.frontmatter.id)
                logger.info("Re-queued INTERRUPTED spec: %s", spec.frontmatter.id)

        return re_queued

    @staticmethod
    def interrupt_active_specs(project_root: str) -> list[str]:
        """Transition IN_PROGRESS specs to INTERRUPTED for graceful shutdown.

        :param project_root: Root directory of the project.
        :returns: List of spec IDs that were interrupted.
        """
        in_progress = list_specs(project_root, status_filter=SpecStatus.IN_PROGRESS)
        interrupted: list[str] = []

        for spec in in_progress:
            if spec.file_path:
                update_spec_status(
                    spec.file_path,
                    SpecStatus.INTERRUPTED,
                    extra_updates={"assigned_to": None},
                )
                interrupted.append(spec.frontmatter.id)
                logger.info("Interrupted active spec: %s", spec.frontmatter.id)

        return interrupted
