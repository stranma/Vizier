"""Metrics tracking for Retrospective analysis.

Computes rejection rate, stuck rate, average retries, and other
improvement metrics from spec lifecycle data.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class SpecMetrics:
    """Aggregated metrics from spec lifecycle data.

    :param total_specs: Total number of specs analyzed.
    :param done_count: Specs that reached DONE status.
    :param rejected_count: Specs that went through REJECTED.
    :param stuck_count: Specs that reached STUCK status.
    :param total_retries: Total retry count across all specs.
    """

    total_specs: int = 0
    done_count: int = 0
    rejected_count: int = 0
    stuck_count: int = 0
    total_retries: int = 0

    @property
    def rejection_rate(self) -> float:
        """Percentage of specs that went through REJECTED before DONE."""
        if self.total_specs == 0:
            return 0.0
        return self.rejected_count / self.total_specs * 100

    @property
    def stuck_rate(self) -> float:
        """Percentage of specs that reached STUCK status."""
        if self.total_specs == 0:
            return 0.0
        return self.stuck_count / self.total_specs * 100

    @property
    def average_retries(self) -> float:
        """Mean retry count per spec."""
        if self.total_specs == 0:
            return 0.0
        return self.total_retries / self.total_specs


def collect_spec_metrics(project_root: str) -> SpecMetrics:
    """Collect metrics from spec state files.

    :param project_root: Project root directory.
    :returns: Aggregated SpecMetrics.
    """
    metrics = SpecMetrics()
    specs_dir = os.path.join(project_root, ".vizier", "specs")

    if not os.path.isdir(specs_dir):
        return metrics

    for spec_id in sorted(os.listdir(specs_dir)):
        state_path = os.path.join(specs_dir, spec_id, "state.json")
        if not os.path.isfile(state_path):
            continue

        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        metrics.total_specs += 1
        status = state.get("status", "")

        if status == "DONE":
            metrics.done_count += 1
        if status == "STUCK":
            metrics.stuck_count += 1

        retry_count = state.get("retry_count", 0)
        metrics.total_retries += retry_count

        if state.get("was_rejected", False) or retry_count > 0:
            metrics.rejected_count += 1

    return metrics


def format_metrics_summary(metrics: SpecMetrics) -> str:
    """Format metrics as a human-readable summary.

    :param metrics: SpecMetrics to format.
    :returns: Formatted summary string.
    """
    return (
        f"Total specs: {metrics.total_specs}\n"
        f"Completed (DONE): {metrics.done_count}\n"
        f"Stuck: {metrics.stuck_count}\n"
        f"Rejection rate: {metrics.rejection_rate:.1f}%\n"
        f"Stuck rate: {metrics.stuck_rate:.1f}%\n"
        f"Average retries: {metrics.average_retries:.1f}"
    )
