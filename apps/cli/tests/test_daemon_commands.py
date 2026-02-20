"""Tests for CLI daemon management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from vizier.cli import main
from vizier.daemon.config import load_project_registry


@pytest.fixture()
def vizier_root(tmp_path: Any) -> str:
    root = tmp_path / "vizier"
    root.mkdir()
    return str(root)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestInit:
    def test_creates_directory_structure(self, runner: CliRunner, vizier_root: str) -> None:
        result = runner.invoke(main, ["init", "--root", vizier_root])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower()

        root = Path(vizier_root)
        assert (root / "workspaces").is_dir()
        assert (root / "reports").is_dir()
        assert (root / "ea").is_dir()
        assert (root / "security").is_dir()
        assert (root / "logs").is_dir()
        assert (root / "config.yaml").exists()
        assert (root / "projects.yaml").exists()

    def test_idempotent(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(main, ["init", "--root", vizier_root])
        assert result.exit_code == 0


class TestRegister:
    def test_registers_project(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(main, ["register", "alpha", "--root", vizier_root])
        assert result.exit_code == 0
        assert "Registered project: alpha" in result.output

        reg = load_project_registry(Path(vizier_root) / "projects.yaml")
        assert reg.get("alpha") is not None

    def test_register_with_repo(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(
            main, ["register", "beta", "--repo", "https://github.com/org/beta.git", "--root", vizier_root]
        )
        assert result.exit_code == 0

        reg = load_project_registry(Path(vizier_root) / "projects.yaml")
        entry = reg.get("beta")
        assert entry is not None
        assert entry.repo_url == "https://github.com/org/beta.git"

    def test_register_with_local_path(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(main, ["register", "gamma", "--local-path", "/projects/gamma", "--root", vizier_root])
        assert result.exit_code == 0

        reg = load_project_registry(Path(vizier_root) / "projects.yaml")
        entry = reg.get("gamma")
        assert entry is not None
        assert entry.local_path == "/projects/gamma"

    def test_register_with_plugin(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(main, ["register", "docs", "--plugin", "documents", "--root", vizier_root])
        assert result.exit_code == 0

        reg = load_project_registry(Path(vizier_root) / "projects.yaml")
        entry = reg.get("docs")
        assert entry is not None
        assert entry.plugin == "documents"

    def test_register_duplicate_fails(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        runner.invoke(main, ["register", "alpha", "--root", vizier_root])
        result = runner.invoke(main, ["register", "alpha", "--root", vizier_root])
        assert result.exit_code != 0


class TestStart:
    def test_start_missing_root(self, runner: CliRunner, tmp_path: Any) -> None:
        missing = str(tmp_path / "nonexistent")
        result = runner.invoke(main, ["start", "--root", missing])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_start_once_mock(self, runner: CliRunner, vizier_root: str) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        runner.invoke(main, ["init", "--root", vizier_root])
        (Path(vizier_root) / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")

        mock_daemon = MagicMock()
        mock_daemon.run_once = AsyncMock(return_value={"test": {"status": "idle"}})

        with patch("vizier.daemon.process.VizierDaemon", return_value=mock_daemon):
            result = runner.invoke(main, ["start", "--root", vizier_root, "--once"])

        assert result.exit_code == 0
        mock_daemon.setup.assert_called_once()
        mock_daemon.run_once.assert_awaited_once()

    def test_start_writes_pid(self, runner: CliRunner, vizier_root: str) -> None:
        from unittest.mock import AsyncMock, MagicMock, patch

        runner.invoke(main, ["init", "--root", vizier_root])
        (Path(vizier_root) / ".env").write_text("ANTHROPIC_API_KEY=sk-test\n", encoding="utf-8")

        mock_daemon = MagicMock()
        mock_daemon.run_forever = AsyncMock(return_value=None)

        pid_file = Path(vizier_root) / "vizier.pid"

        with patch("vizier.daemon.process.VizierDaemon", return_value=mock_daemon):
            result = runner.invoke(main, ["start", "--root", vizier_root])

        mock_daemon.setup.assert_called_once()
        assert not pid_file.exists()


class TestStop:
    def test_stop_no_pid_fails(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        result = runner.invoke(main, ["stop", "--root", vizier_root])
        assert result.exit_code != 0
        assert "No running daemon" in result.output

    def test_stop_stale_pid(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        pid_file = Path(vizier_root) / "vizier.pid"
        pid_file.write_text("999999999", encoding="utf-8")
        result = runner.invoke(main, ["stop", "--root", vizier_root])
        assert "not found" in result.output.lower()


class TestStatus:
    def test_status_not_initialized(self, runner: CliRunner, tmp_path: Any) -> None:
        result = runner.invoke(main, ["status", "--root", str(tmp_path / "missing")])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_status_shows_info(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        runner.invoke(main, ["register", "alpha", "--root", vizier_root])
        result = runner.invoke(main, ["status", "--root", vizier_root])
        assert result.exit_code == 0
        assert "Vizier Status" in result.output
        assert "alpha" in result.output
        assert "stopped" in result.output

    def test_status_with_heartbeat(self, runner: CliRunner, vizier_root: str) -> None:
        runner.invoke(main, ["init", "--root", vizier_root])
        hb_path = Path(vizier_root) / "heartbeat.json"
        hb_path.write_text(json.dumps({"timestamp": "2026-01-01T00:00:00Z", "pid": 1234}), encoding="utf-8")
        result = runner.invoke(main, ["status", "--root", vizier_root])
        assert result.exit_code == 0
        assert "heartbeat" in result.output.lower()
