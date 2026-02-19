"""Tests for Retrospective metrics tracking."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003

from vizier.core.agents.retrospective.metrics import (
    SpecMetrics,
    collect_spec_metrics,
    format_metrics_summary,
)


class TestSpecMetrics:
    def test_rejection_rate_empty(self) -> None:
        metrics = SpecMetrics()
        assert metrics.rejection_rate == 0.0

    def test_rejection_rate(self) -> None:
        metrics = SpecMetrics(total_specs=10, rejected_count=3)
        assert metrics.rejection_rate == 30.0

    def test_stuck_rate_empty(self) -> None:
        metrics = SpecMetrics()
        assert metrics.stuck_rate == 0.0

    def test_stuck_rate(self) -> None:
        metrics = SpecMetrics(total_specs=20, stuck_count=2)
        assert metrics.stuck_rate == 10.0

    def test_average_retries_empty(self) -> None:
        metrics = SpecMetrics()
        assert metrics.average_retries == 0.0

    def test_average_retries(self) -> None:
        metrics = SpecMetrics(total_specs=5, total_retries=10)
        assert metrics.average_retries == 2.0


class TestCollectSpecMetrics:
    def test_empty_project(self, tmp_path: Path) -> None:
        metrics = collect_spec_metrics(str(tmp_path))
        assert metrics.total_specs == 0

    def test_counts_done_specs(self, tmp_path: Path) -> None:
        for sid, status in [("001", "DONE"), ("002", "DONE"), ("003", "IN_PROGRESS")]:
            spec_dir = tmp_path / ".vizier" / "specs" / sid
            spec_dir.mkdir(parents=True)
            (spec_dir / "state.json").write_text(json.dumps({"status": status}))

        metrics = collect_spec_metrics(str(tmp_path))
        assert metrics.total_specs == 3
        assert metrics.done_count == 2

    def test_counts_stuck_specs(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "STUCK"}))

        metrics = collect_spec_metrics(str(tmp_path))
        assert metrics.stuck_count == 1

    def test_counts_rejections(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text(json.dumps({"status": "DONE", "was_rejected": True, "retry_count": 2}))

        metrics = collect_spec_metrics(str(tmp_path))
        assert metrics.rejected_count == 1
        assert metrics.total_retries == 2

    def test_handles_invalid_json(self, tmp_path: Path) -> None:
        spec_dir = tmp_path / ".vizier" / "specs" / "001"
        spec_dir.mkdir(parents=True)
        (spec_dir / "state.json").write_text("{invalid")

        metrics = collect_spec_metrics(str(tmp_path))
        assert metrics.total_specs == 0


class TestFormatMetricsSummary:
    def test_format(self) -> None:
        metrics = SpecMetrics(
            total_specs=10,
            done_count=7,
            rejected_count=3,
            stuck_count=1,
            total_retries=5,
        )
        summary = format_metrics_summary(metrics)
        assert "Total specs: 10" in summary
        assert "30.0%" in summary
        assert "10.0%" in summary
