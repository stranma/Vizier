"""Tests for budget tracking tools (Phase 10: Budget Tracking Lite).

Tests budget_record and budget_summary tools for cost visibility.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vizier_mcp.tools.budget import budget_record, budget_summary

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


class TestBudgetRecord:
    """Tests for budget_record tool."""

    def test_basic_record(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        assert result["recorded"] is True
        assert result["event"]["event_type"] == "haiku_eval"
        assert result["event"]["cost_estimate"] == 0.001

    def test_record_with_spec_id(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "spec_attempt", 0.05, spec_id="001-auth")
        assert result["recorded"] is True
        assert result["event"]["spec_id"] == "001-auth"

    def test_record_with_metadata(self, config: ServerConfig, project_dir: Path) -> None:
        meta = {"model": "haiku", "tokens": 150}
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.002, metadata=meta)
        assert result["recorded"] is True
        assert result["event"]["metadata"]["model"] == "haiku"
        assert result["event"]["metadata"]["tokens"] == 150

    def test_negative_cost_rejected(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "custom", -0.01)
        assert "error" in result
        assert "cost_estimate" in result["error"]

    def test_zero_cost_ok(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "custom", 0.0)
        assert result["recorded"] is True
        assert result["event"]["cost_estimate"] == 0.0

    def test_directory_creation(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        budget_dir = project_dir / ".vizier" / "budget"
        assert budget_dir.exists()
        assert (budget_dir / "events.jsonl").exists()

    def test_multiple_events_appended(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        budget_record(config, PROJECT_ID, "spec_attempt", 0.05)
        budget_record(config, PROJECT_ID, "web_fetch", 0.003)
        events_file = project_dir / ".vizier" / "budget" / "events.jsonl"
        lines = [ln for ln in events_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 3
        for line in lines:
            data = json.loads(line)
            assert "event_type" in data

    def test_record_with_agent_role(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.001, agent_role="worker")
        assert result["recorded"] is True
        assert result["event"]["agent_role"] == "worker"

    def test_record_custom_event_type(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "my_custom_type", 0.1)
        assert result["recorded"] is True
        assert result["event"]["event_type"] == "my_custom_type"


class TestBudgetSummary:
    """Tests for budget_summary tool."""

    def test_empty_project(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_summary(config, PROJECT_ID)
        assert result["project_id"] == PROJECT_ID
        assert result["total_cost"] == 0.0
        assert result["event_count"] == 0
        assert result["by_event_type"] == {}
        assert result["by_spec"] == {}

    def test_totals(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        budget_record(config, PROJECT_ID, "haiku_eval", 0.002)
        budget_record(config, PROJECT_ID, "spec_attempt", 0.05)
        result = budget_summary(config, PROJECT_ID)
        assert result["total_cost"] == 0.053
        assert result["event_count"] == 3

    def test_by_event_type_breakdown(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        budget_record(config, PROJECT_ID, "haiku_eval", 0.002)
        budget_record(config, PROJECT_ID, "web_fetch", 0.01)
        result = budget_summary(config, PROJECT_ID)
        assert result["by_event_type"]["haiku_eval"] == 0.003
        assert result["by_event_type"]["web_fetch"] == 0.01

    def test_by_spec_breakdown(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001, spec_id="001-auth")
        budget_record(config, PROJECT_ID, "spec_attempt", 0.05, spec_id="001-auth")
        budget_record(config, PROJECT_ID, "haiku_eval", 0.002, spec_id="002-api")
        result = budget_summary(config, PROJECT_ID)
        assert result["by_spec"]["001-auth"] == 0.051
        assert result["by_spec"]["002-api"] == 0.002

    def test_filter_by_spec_id(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001, spec_id="001-auth")
        budget_record(config, PROJECT_ID, "haiku_eval", 0.002, spec_id="002-api")
        result = budget_summary(config, PROJECT_ID, spec_id="001-auth")
        assert result["event_count"] == 1
        assert result["total_cost"] == 0.001

    def test_filter_by_event_type(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        budget_record(config, PROJECT_ID, "web_fetch", 0.01)
        result = budget_summary(config, PROJECT_ID, event_type="haiku_eval")
        assert result["event_count"] == 1
        assert result["total_cost"] == 0.001

    def test_include_events_flag(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        result_no_events = budget_summary(config, PROJECT_ID, include_events=False)
        assert "events" not in result_no_events
        result_with_events = budget_summary(config, PROJECT_ID, include_events=True)
        assert "events" in result_with_events
        assert len(result_with_events["events"]) == 1

    def test_nonexistent_project(self, config: ServerConfig) -> None:
        result = budget_summary(config, "nonexistent-project")
        assert result["total_cost"] == 0.0
        assert result["event_count"] == 0


class TestBudgetIntegration:
    """Integration tests for budget tracking workflows."""

    def test_haiku_cost_tracking(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.0003, spec_id="001-auth", agent_role="sentinel")
        budget_record(config, PROJECT_ID, "haiku_eval", 0.0005, spec_id="001-auth", agent_role="sentinel")
        budget_record(config, PROJECT_ID, "spec_attempt", 0.02, spec_id="001-auth", agent_role="worker")

        result = budget_summary(config, PROJECT_ID, spec_id="001-auth", include_events=True)
        assert result["event_count"] == 3
        assert result["total_cost"] == 0.0208
        assert result["by_event_type"]["haiku_eval"] == 0.0008
        assert result["by_event_type"]["spec_attempt"] == 0.02
        assert len(result["events"]) == 3

    def test_multi_spec_visibility(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "spec_attempt", 0.05, spec_id="001-auth")
        budget_record(config, PROJECT_ID, "spec_attempt", 0.03, spec_id="002-api")
        budget_record(config, PROJECT_ID, "web_fetch", 0.005, spec_id="002-api")

        result = budget_summary(config, PROJECT_ID)
        assert result["total_cost"] == 0.085
        assert result["by_spec"]["001-auth"] == 0.05
        assert result["by_spec"]["002-api"] == 0.035
        assert result["event_count"] == 3

    def test_since_minutes_filter(self, config: ServerConfig, project_dir: Path) -> None:
        budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        result = budget_summary(config, PROJECT_ID, since_minutes=5)
        assert result["event_count"] == 1
        assert result["total_cost"] == 0.001
