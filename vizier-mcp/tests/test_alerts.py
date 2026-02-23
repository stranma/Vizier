"""Tests for alert infrastructure (Phase 12: Empire Briefing + Alerts).

Tests AlertData model, budget threshold alerts, deduplication,
and alert reading from system_get_status.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vizier_mcp.config import BudgetConfig, ServerConfig
from vizier_mcp.logging_structured import StructuredLogger
from vizier_mcp.models.alerts import AlertData, AlertSeverity, AlertType
from vizier_mcp.tools.budget import budget_record
from vizier_mcp.tools.status import system_get_status

if TYPE_CHECKING:
    from pathlib import Path

PROJECT_ID = "test-project"


class TestAlertDataModel:
    """Tests for AlertData Pydantic model."""

    def test_create_alert(self) -> None:
        alert = AlertData(
            alert_type="budget_soft_limit",
            project_id="proj-1",
            message="Budget exceeded",
            severity=AlertSeverity.warning,
        )
        assert alert.alert_type == "budget_soft_limit"
        assert alert.project_id == "proj-1"
        assert alert.severity == AlertSeverity.warning
        assert alert.acknowledged is False
        assert alert.data == {}

    def test_alert_with_data(self) -> None:
        alert = AlertData(
            alert_type="budget_hard_limit",
            project_id="proj-1",
            message="Hard limit hit",
            severity=AlertSeverity.critical,
            data={"total_cost": 25.0, "hard_limit": 20.0},
        )
        assert alert.data["total_cost"] == 25.0
        assert alert.severity == AlertSeverity.critical

    def test_alert_serialization(self) -> None:
        alert = AlertData(
            alert_type="budget_soft_limit",
            project_id="proj-1",
            message="test",
            severity=AlertSeverity.warning,
        )
        dumped = json.loads(alert.model_dump_json())
        assert dumped["alert_type"] == "budget_soft_limit"
        assert dumped["acknowledged"] is False
        assert "created_at" in dumped

    def test_alert_type_enum(self) -> None:
        assert AlertType.budget_soft_limit == "budget_soft_limit"
        assert AlertType.budget_hard_limit == "budget_hard_limit"

    def test_severity_enum(self) -> None:
        assert AlertSeverity.warning == "warning"
        assert AlertSeverity.critical == "critical"


class TestBudgetThresholds:
    """Tests for budget threshold alert generation."""

    def test_below_soft_limit_no_alert(self, config: ServerConfig, project_dir: Path) -> None:
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.001)
        assert result["recorded"] is True
        assert "alerts_triggered" not in result

    def test_soft_limit_triggers_warning(self, tmp_path: Path, project_dir_factory: None) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "haiku_eval", 0.005)
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.006)
        assert result["recorded"] is True
        assert "alerts_triggered" in result
        assert "budget_soft_limit" in result["alerts_triggered"]

    def test_hard_limit_triggers_critical(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=0.02),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "spec_attempt", 0.015)
        result = budget_record(config, PROJECT_ID, "spec_attempt", 0.01)
        assert result["recorded"] is True
        assert "alerts_triggered" in result
        assert "budget_hard_limit" in result["alerts_triggered"]

    def test_alert_file_written(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "haiku_eval", 0.02)
        assert config.alerts_dir is not None
        alert_files = list(config.alerts_dir.glob("*.json"))
        assert len(alert_files) == 1
        data = json.loads(alert_files[0].read_text())
        assert data["alert_type"] == "budget_soft_limit"
        assert data["severity"] == "warning"
        assert data["project_id"] == PROJECT_ID

    def test_hard_limit_alert_file_content(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.005, hard_limit_usd=0.01),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "spec_attempt", 0.015)
        assert config.alerts_dir is not None
        alert_files = list(config.alerts_dir.glob("*.json"))
        assert len(alert_files) == 1
        data = json.loads(alert_files[0].read_text())
        assert data["alert_type"] == "budget_hard_limit"
        assert data["severity"] == "critical"


class TestAlertDeduplication:
    """Tests for alert deduplication logic."""

    def test_duplicate_alert_not_written(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "haiku_eval", 0.02)
        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.01)
        assert "alerts_triggered" not in result

        assert config.alerts_dir is not None
        alert_files = list(config.alerts_dir.glob("*.json"))
        assert len(alert_files) == 1

    def test_acknowledged_alert_allows_new(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()

        budget_record(config, PROJECT_ID, "haiku_eval", 0.02)

        assert config.alerts_dir is not None
        alert_files = list(config.alerts_dir.glob("*.json"))
        assert len(alert_files) == 1
        data = json.loads(alert_files[0].read_text())
        data["acknowledged"] = True
        alert_files[0].write_text(json.dumps(data))

        result = budget_record(config, PROJECT_ID, "haiku_eval", 0.01)
        assert "alerts_triggered" in result
        assert len(list(config.alerts_dir.glob("*.json"))) == 2

    def test_different_projects_get_separate_alerts(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        for pid in ["proj-a", "proj-b"]:
            proj = config.projects_dir / pid  # type: ignore[operator]
            proj.mkdir(parents=True)
            (proj / "specs").mkdir()

        budget_record(config, "proj-a", "haiku_eval", 0.02)
        budget_record(config, "proj-b", "haiku_eval", 0.02)

        assert config.alerts_dir is not None
        alert_files = list(config.alerts_dir.glob("*.json"))
        assert len(alert_files) == 2


class TestStatusAlerts:
    """Tests for alerts appearing in system_get_status."""

    @pytest.fixture
    def slog(self, config: ServerConfig) -> StructuredLogger:
        assert config.log_dir is not None
        return StructuredLogger(config.log_dir)

    def test_no_alerts_returns_empty(self, config: ServerConfig, slog: StructuredLogger, project_dir: Path) -> None:
        result = system_get_status(config, slog, "0.12.0", 21)
        assert result["alerts"] == []

    def test_alerts_included_in_status(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        log_dir = tmp_path / "vizier" / "logs"
        log_dir.mkdir(parents=True)
        config_with_logs = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=config.projects_dir,
            budget=config.budget,
            alerts_dir=config.alerts_dir,
            log_dir=log_dir,
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()
        slog = StructuredLogger(log_dir)

        budget_record(config_with_logs, PROJECT_ID, "haiku_eval", 0.02)

        result = system_get_status(config_with_logs, slog, "0.12.0", 21)
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["alert_type"] == "budget_soft_limit"

    def test_acknowledged_alerts_excluded(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        log_dir = tmp_path / "vizier" / "logs"
        log_dir.mkdir(parents=True)
        config_with_logs = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=config.projects_dir,
            budget=config.budget,
            alerts_dir=config.alerts_dir,
            log_dir=log_dir,
        )
        proj = config.projects_dir / PROJECT_ID  # type: ignore[operator]
        proj.mkdir(parents=True)
        (proj / "specs").mkdir()
        slog = StructuredLogger(log_dir)

        budget_record(config_with_logs, PROJECT_ID, "haiku_eval", 0.02)

        assert config_with_logs.alerts_dir is not None
        alert_files = list(config_with_logs.alerts_dir.glob("*.json"))
        data = json.loads(alert_files[0].read_text())
        data["acknowledged"] = True
        alert_files[0].write_text(json.dumps(data))

        result = system_get_status(config_with_logs, slog, "0.12.0", 21)
        assert result["alerts"] == []

    def test_alerts_filtered_by_project(self, tmp_path: Path) -> None:
        config = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=tmp_path / "vizier" / "projects",
            budget=BudgetConfig(soft_limit_usd=0.01, hard_limit_usd=1.0),
            alerts_dir=tmp_path / "vizier" / "alerts",
        )
        log_dir = tmp_path / "vizier" / "logs"
        log_dir.mkdir(parents=True)
        config_with_logs = ServerConfig(
            vizier_root=tmp_path / "vizier",
            projects_dir=config.projects_dir,
            budget=config.budget,
            alerts_dir=config.alerts_dir,
            log_dir=log_dir,
        )
        for pid in ["proj-a", "proj-b"]:
            proj = config.projects_dir / pid  # type: ignore[operator]
            proj.mkdir(parents=True)
            (proj / "specs").mkdir()
        slog = StructuredLogger(log_dir)

        budget_record(config_with_logs, "proj-a", "haiku_eval", 0.02)
        budget_record(config_with_logs, "proj-b", "haiku_eval", 0.02)

        result = system_get_status(config_with_logs, slog, "0.12.0", 21, project_id="proj-a")
        assert len(result["alerts"]) == 1
        assert result["alerts"][0]["project_id"] == "proj-a"


@pytest.fixture
def project_dir_factory() -> None:
    """Marker fixture so tests can create their own project dirs."""
