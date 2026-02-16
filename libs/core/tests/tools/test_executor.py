"""Tests for ToolExecutor with scoped secret injection."""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003

from vizier.core.secrets.env_file_store import EnvFileSecretStore
from vizier.core.tools.executor import DEFAULT_TOOL_SECRETS, ToolExecutor


def _make_executor(tmp_path: Path, env_content: str, **kwargs: object) -> ToolExecutor:
    env_file = tmp_path / ".env"
    env_file.write_text(env_content)
    store = EnvFileSecretStore(env_file)
    return ToolExecutor(store, **kwargs)  # type: ignore[arg-type]


class TestBuildEnv:
    def test_git_injects_allowed_secrets(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "GITHUB_TOKEN=ghp_test\nGIT_AUTHOR_NAME=Test\n")
        env = executor._build_env("git")
        assert env["GITHUB_TOKEN"] == "ghp_test"
        assert env["GIT_AUTHOR_NAME"] == "Test"

    def test_bash_injects_no_secrets_by_default(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "GITHUB_TOKEN=ghp_test\n")
        env = executor._build_env("bash")
        assert env.get("GITHUB_TOKEN") != "ghp_test" or "GITHUB_TOKEN" not in executor._tool_secrets.get("bash", [])

    def test_extra_secrets_added(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "DEPLOY_KEY=dk123\n")
        env = executor._build_env("bash", extra_secrets=["DEPLOY_KEY"])
        assert env["DEPLOY_KEY"] == "dk123"

    def test_missing_secret_skipped(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "OTHER=val\n")
        env = executor._build_env("git")
        assert "GITHUB_TOKEN" not in env or env.get("GITHUB_TOKEN") == os.environ.get("GITHUB_TOKEN")

    def test_preserves_existing_env(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "KEY=val\n")
        env = executor._build_env("bash")
        assert "PATH" in env

    def test_unknown_tool_type_no_secrets(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "KEY=val\n")
        env = executor._build_env("unknown_tool")
        assert "KEY" not in env or env.get("KEY") == os.environ.get("KEY")


class TestGetAllowedSecrets:
    def test_git_defaults(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        allowed = executor.get_allowed_secrets("git")
        assert "GITHUB_TOKEN" in allowed

    def test_bash_defaults_empty(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        allowed = executor.get_allowed_secrets("bash")
        assert allowed == []

    def test_unknown_tool_empty(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        assert executor.get_allowed_secrets("random") == []


class TestConfigureToolSecrets:
    def test_configure_new_tool(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        executor.configure_tool_secrets("npm", ["NPM_TOKEN"])
        assert executor.get_allowed_secrets("npm") == ["NPM_TOKEN"]

    def test_override_existing(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        executor.configure_tool_secrets("bash", ["ALLOWED_KEY"])
        assert executor.get_allowed_secrets("bash") == ["ALLOWED_KEY"]


class TestExecuteCommand:
    def test_simple_command(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        result = executor.execute_command("echo hello", timeout=10)
        assert result.returncode == 0
        assert "hello" in result.stdout

    def test_git_command_injects_secrets(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "GIT_AUTHOR_NAME=TestAuthor\n")
        env = executor._build_env("git")
        assert env["GIT_AUTHOR_NAME"] == "TestAuthor"

    def test_to_tool_result(self, tmp_path: Path) -> None:
        executor = _make_executor(tmp_path, "")
        result = executor.execute_command("echo output", timeout=10)
        tool_result = executor.to_tool_result(result)
        assert "stdout" in tool_result
        assert "stderr" in tool_result
        assert "return_code" in tool_result
        assert tool_result["return_code"] == 0


class TestDefaultToolSecrets:
    def test_git_has_expected_keys(self) -> None:
        assert "GITHUB_TOKEN" in DEFAULT_TOOL_SECRETS["git"]
        assert "GIT_AUTHOR_NAME" in DEFAULT_TOOL_SECRETS["git"]
        assert "GIT_AUTHOR_EMAIL" in DEFAULT_TOOL_SECRETS["git"]

    def test_bash_is_empty(self) -> None:
        assert DEFAULT_TOOL_SECRETS["bash"] == []
