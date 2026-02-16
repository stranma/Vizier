"""Tests for daemon configuration loading and project registry."""

from __future__ import annotations

from typing import Any

import pytest
import yaml

from vizier.daemon.config import (
    AutonomyConfig,
    DaemonConfig,
    ProjectEntry,
    ProjectRegistry,
    TelegramConfig,
    load_daemon_config,
    load_project_registry,
    save_project_registry,
)


class TestAutonomyConfig:
    def test_defaults(self) -> None:
        config = AutonomyConfig()
        assert config.stage == 1
        assert config.auto_approve_plugins == []
        assert config.stage_history == []

    def test_stage_bounds(self) -> None:
        config = AutonomyConfig(stage=4)
        assert config.stage == 4

    def test_stage_too_low(self) -> None:
        with pytest.raises(ValueError):
            AutonomyConfig(stage=0)

    def test_stage_too_high(self) -> None:
        with pytest.raises(ValueError):
            AutonomyConfig(stage=5)


class TestTelegramConfig:
    def test_defaults(self) -> None:
        config = TelegramConfig()
        assert config.token == ""
        assert config.allowed_user_ids == []


class TestDaemonConfig:
    def test_defaults(self) -> None:
        config = DaemonConfig()
        assert config.vizier_root == "/opt/vizier"
        assert config.max_concurrent_agents == 5
        assert config.reconciliation_interval_seconds == 15
        assert config.heartbeat_path == "heartbeat.json"
        assert config.monthly_budget_usd == 100.0
        assert config.health_check_port == 8080
        assert config.log_rotation_max_bytes == 10 * 1024 * 1024
        assert config.log_rotation_backup_count == 5

    def test_custom_values(self) -> None:
        config = DaemonConfig(
            vizier_root="/srv/vizier",
            max_concurrent_agents=10,
            reconciliation_interval_seconds=30,
            monthly_budget_usd=500.0,
        )
        assert config.vizier_root == "/srv/vizier"
        assert config.max_concurrent_agents == 10
        assert config.reconciliation_interval_seconds == 30
        assert config.monthly_budget_usd == 500.0

    def test_nested_autonomy(self) -> None:
        config = DaemonConfig(autonomy=AutonomyConfig(stage=3))
        assert config.autonomy.stage == 3

    def test_nested_telegram(self) -> None:
        config = DaemonConfig(telegram=TelegramConfig(token="test-token"))
        assert config.telegram.token == "test-token"


class TestProjectEntry:
    def test_defaults(self) -> None:
        entry = ProjectEntry(name="alpha")
        assert entry.name == "alpha"
        assert entry.repo_url == ""
        assert entry.local_path == ""
        assert entry.plugin == "software"
        assert entry.active is True

    def test_full_entry(self) -> None:
        entry = ProjectEntry(
            name="beta",
            repo_url="https://github.com/org/beta.git",
            local_path="/opt/vizier/workspaces/beta",
            plugin="documents",
            active=False,
        )
        assert entry.name == "beta"
        assert entry.plugin == "documents"
        assert entry.active is False


class TestProjectRegistry:
    def test_empty_registry(self) -> None:
        reg = ProjectRegistry()
        assert reg.projects == []
        assert reg.active_projects() == []

    def test_add_project(self) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha"))
        assert len(reg.projects) == 1
        assert reg.get("alpha") is not None

    def test_add_duplicate_raises(self) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha"))
        with pytest.raises(ValueError, match="already registered"):
            reg.add(ProjectEntry(name="alpha"))

    def test_get_nonexistent(self) -> None:
        reg = ProjectRegistry()
        assert reg.get("missing") is None

    def test_remove_project(self) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha"))
        assert reg.remove("alpha") is True
        assert reg.get("alpha") is None

    def test_remove_nonexistent(self) -> None:
        reg = ProjectRegistry()
        assert reg.remove("missing") is False

    def test_active_projects_filter(self) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="active1"))
        reg.add(ProjectEntry(name="inactive", active=False))
        reg.add(ProjectEntry(name="active2"))
        active = reg.active_projects()
        assert len(active) == 2
        names = [p.name for p in active]
        assert "active1" in names
        assert "active2" in names
        assert "inactive" not in names


class TestLoadDaemonConfig:
    def test_missing_file_returns_defaults(self, tmp_path: Any) -> None:
        config = load_daemon_config(tmp_path / "missing.yaml")
        assert config.vizier_root == "/opt/vizier"

    def test_empty_file_returns_defaults(self, tmp_path: Any) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        config = load_daemon_config(config_file)
        assert config.vizier_root == "/opt/vizier"

    def test_loads_from_yaml(self, tmp_path: Any) -> None:
        config_file = tmp_path / "config.yaml"
        data = {
            "vizier_root": "/srv/vizier",
            "max_concurrent_agents": 8,
            "monthly_budget_usd": 250.0,
        }
        config_file.write_text(yaml.dump(data), encoding="utf-8")
        config = load_daemon_config(config_file)
        assert config.vizier_root == "/srv/vizier"
        assert config.max_concurrent_agents == 8
        assert config.monthly_budget_usd == 250.0

    def test_env_var_substitution(self, tmp_path: Any, monkeypatch: Any) -> None:
        monkeypatch.setenv("VIZIER_ROOT_DIR", "/custom/vizier")
        config_file = tmp_path / "config.yaml"
        config_file.write_text('vizier_root: "${VIZIER_ROOT_DIR}"\n', encoding="utf-8")
        config = load_daemon_config(config_file)
        assert config.vizier_root == "/custom/vizier"


class TestProjectRegistryIO:
    def test_load_missing_file(self, tmp_path: Any) -> None:
        reg = load_project_registry(tmp_path / "missing.yaml")
        assert reg.projects == []

    def test_load_empty_file(self, tmp_path: Any) -> None:
        reg_file = tmp_path / "projects.yaml"
        reg_file.write_text("", encoding="utf-8")
        reg = load_project_registry(reg_file)
        assert reg.projects == []

    def test_save_and_load_roundtrip(self, tmp_path: Any) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha", repo_url="https://github.com/org/alpha.git"))
        reg.add(ProjectEntry(name="beta", plugin="documents", active=False))

        reg_file = tmp_path / "projects.yaml"
        save_project_registry(reg, reg_file)

        loaded = load_project_registry(reg_file)
        assert len(loaded.projects) == 2
        alpha = loaded.get("alpha")
        assert alpha is not None
        assert alpha.repo_url == "https://github.com/org/alpha.git"
        beta = loaded.get("beta")
        assert beta is not None
        assert beta.active is False

    def test_save_creates_parent_dirs(self, tmp_path: Any) -> None:
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="test"))
        nested = tmp_path / "deep" / "nested" / "projects.yaml"
        save_project_registry(reg, nested)
        assert nested.exists()

    def test_atomic_write(self, tmp_path: Any) -> None:
        reg_file = tmp_path / "projects.yaml"
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha"))
        save_project_registry(reg, reg_file)
        tmp_file = reg_file.with_suffix(".yaml.tmp")
        assert not tmp_file.exists()
