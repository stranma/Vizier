"""Tests for SecretCheckTool."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from vizier.core.secrets.env_file_store import EnvFileSecretStore
from vizier.core.tools.secret_check import SecretCheckTool


def _make_tool(tmp_path: Path, env_content: str) -> SecretCheckTool:
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)
    store = EnvFileSecretStore(env_file)
    return SecretCheckTool(store)


class TestCheckSecret:
    def test_existing_secret(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "GITHUB_TOKEN=ghp_test\n")
        result = tool.check_secret("GITHUB_TOKEN")
        assert result["key"] == "GITHUB_TOKEN"
        assert result["exists"] is True
        assert result["has_value"] is True

    def test_missing_secret(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "OTHER=val\n")
        result = tool.check_secret("GITHUB_TOKEN")
        assert result["exists"] is False
        assert result["has_value"] is False

    def test_empty_secret(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "EMPTY_KEY=\n")
        result = tool.check_secret("EMPTY_KEY")
        assert result["exists"] is True
        assert result["has_value"] is False

    def test_never_exposes_value(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "MY_SECRET=super-secret-value\n")
        result = tool.check_secret("MY_SECRET")
        assert "super-secret-value" not in str(result)
        assert "value" not in result or result.get("value") is None


class TestListConfiguredSecrets:
    def test_lists_all_keys(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "A_KEY=1\nB_KEY=2\nC_KEY=3\n")
        result = tool.list_configured_secrets()
        assert result["secrets"] == ["A_KEY", "B_KEY", "C_KEY"]
        assert result["count"] == 3

    def test_empty_store(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "")
        result = tool.list_configured_secrets()
        assert result["secrets"] == []
        assert result["count"] == 0

    def test_values_never_in_result(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "API_KEY=secret123\n")
        result = tool.list_configured_secrets()
        assert "secret123" not in str(result)


class TestExecuteAction:
    def test_check_action(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "KEY=val\n")
        result = tool.execute("check", key="KEY")
        assert result["exists"] is True

    def test_list_action(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "KEY=val\n")
        result = tool.execute("list")
        assert "secrets" in result

    def test_check_requires_key(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "KEY=val\n")
        with pytest.raises(ValueError, match="key"):
            tool.execute("check")

    def test_unknown_action(self, tmp_path: Path) -> None:
        tool = _make_tool(tmp_path, "KEY=val\n")
        with pytest.raises(ValueError, match="Unknown action"):
            tool.execute("unknown")
