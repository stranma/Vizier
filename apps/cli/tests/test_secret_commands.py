"""Tests for CLI secret management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from vizier.cli import main


@pytest.fixture()
def vizier_root(tmp_path: Any) -> str:
    root = tmp_path / "vizier"
    root.mkdir()
    return str(root)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestSecretList:
    def test_no_secrets(self, runner: CliRunner, vizier_root: str) -> None:
        result = runner.invoke(main, ["secret", "list", "--root", vizier_root])
        assert result.exit_code == 0
        assert "No secrets configured" in result.output

    def test_lists_configured_secrets(self, runner: CliRunner, vizier_root: str) -> None:
        env_file = Path(vizier_root) / ".env"
        env_file.write_text("API_KEY=sk-123\nDB_HOST=localhost\n")

        result = runner.invoke(main, ["secret", "list", "--root", vizier_root])
        assert result.exit_code == 0
        assert "API_KEY" in result.output
        assert "DB_HOST" in result.output
        assert "sk-123" not in result.output

    def test_shows_status(self, runner: CliRunner, vizier_root: str) -> None:
        env_file = Path(vizier_root) / ".env"
        env_file.write_text("FILLED=value\nEMPTY=\n")

        result = runner.invoke(main, ["secret", "list", "--root", vizier_root])
        assert result.exit_code == 0
        assert "[set]" in result.output
        assert "[empty]" in result.output


class TestSecretCheck:
    def test_existing_secret(self, runner: CliRunner, vizier_root: str) -> None:
        env_file = Path(vizier_root) / ".env"
        env_file.write_text("MY_KEY=value\n")

        result = runner.invoke(main, ["secret", "check", "MY_KEY", "--root", vizier_root])
        assert result.exit_code == 0
        assert "Exists: yes" in result.output
        assert "Has value: yes" in result.output

    def test_missing_secret(self, runner: CliRunner, vizier_root: str) -> None:
        result = runner.invoke(main, ["secret", "check", "MISSING", "--root", vizier_root])
        assert result.exit_code == 0
        assert "Exists: no" in result.output
        assert "Has value: no" in result.output
        assert "To configure" in result.output


class TestSecretSet:
    def test_set_new_secret(self, runner: CliRunner, vizier_root: str) -> None:
        result = runner.invoke(main, ["secret", "set", "NEW_KEY", "--root", vizier_root], input="myvalue\n")
        assert result.exit_code == 0
        assert "saved" in result.output

        env_file = Path(vizier_root) / ".env"
        content = env_file.read_text(encoding="utf-8")
        assert "NEW_KEY=myvalue" in content

    def test_update_existing_secret(self, runner: CliRunner, vizier_root: str) -> None:
        env_file = Path(vizier_root) / ".env"
        env_file.write_text("OLD_KEY=old_val\nTARGET=original\nOTHER=keep\n")

        result = runner.invoke(main, ["secret", "set", "TARGET", "--root", vizier_root], input="updated\n")
        assert result.exit_code == 0

        content = env_file.read_text(encoding="utf-8")
        assert "TARGET=updated" in content
        assert "original" not in content
        assert "OLD_KEY=old_val" in content
        assert "OTHER=keep" in content

    def test_empty_value_not_saved(self, runner: CliRunner, vizier_root: str) -> None:
        result = runner.invoke(main, ["secret", "set", "KEY", "--root", vizier_root], input="\n")
        assert result.exit_code == 0
        assert "Empty value" in result.output or not (Path(vizier_root) / ".env").exists()
