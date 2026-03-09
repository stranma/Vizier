"""Tests for project_init MCP tool.

Tests cover validation, scaffold/clone flows, devcontainer fetching,
template substitution, and cleanup on failure.
All git operations are mocked via asyncio.create_subprocess_exec.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
import yaml

from vizier_mcp.tools.project import (
    _TEMPLATES_DIR,
    _copy_template_dir,
    _substitute_template,
    _validate_project_id,
    project_init,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig


def _mock_subprocess(returncode: int = 0, stdout: bytes = b"", stderr: bytes = b"") -> AsyncMock:
    """Create a mock async subprocess."""
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


class TestValidation:
    """Tests for input validation."""

    def test_empty_project_id(self) -> None:
        assert _validate_project_id("") is not None

    def test_too_long_project_id(self) -> None:
        assert _validate_project_id("a" * 64) is not None

    def test_valid_project_id(self) -> None:
        assert _validate_project_id("my-project-1") is None

    def test_single_char_project_id(self) -> None:
        assert _validate_project_id("a") is None

    def test_uppercase_rejected(self) -> None:
        assert _validate_project_id("MyProject") is not None

    def test_leading_hyphen_rejected(self) -> None:
        assert _validate_project_id("-foo") is not None

    def test_trailing_hyphen_rejected(self) -> None:
        assert _validate_project_id("foo-") is not None

    def test_special_chars_rejected(self) -> None:
        assert _validate_project_id("foo_bar") is not None

    @pytest.mark.anyio
    async def test_invalid_source(self, config: ServerConfig) -> None:
        result = await project_init(config, "test-proj", "invalid", "python")
        assert "error" in result
        assert "Invalid source" in result["error"]

    @pytest.mark.anyio
    async def test_clone_missing_git_url(self, config: ServerConfig) -> None:
        result = await project_init(config, "test-proj", "clone", "python")
        assert "error" in result
        assert "git_url is required" in result["error"]

    @pytest.mark.anyio
    async def test_unsupported_language(self, config: ServerConfig) -> None:
        result = await project_init(config, "test-proj", "scaffold", "rust")
        assert "error" in result
        assert "Unsupported language" in result["error"]

    @pytest.mark.anyio
    async def test_duplicate_project(self, config: ServerConfig) -> None:
        assert config.projects_dir is not None
        (config.projects_dir / "existing-proj").mkdir()
        result = await project_init(config, "existing-proj", "scaffold", "python")
        assert "error" in result
        assert "already exists" in result["error"]

    @pytest.mark.anyio
    async def test_duplicate_repo(self, config: ServerConfig) -> None:
        assert config.repos_dir is not None
        (config.repos_dir / "existing-repo").mkdir(parents=True)
        result = await project_init(config, "existing-repo", "scaffold", "python")
        assert "error" in result
        assert "already exists" in result["error"]


class TestTemplateHelpers:
    """Tests for template substitution and copying."""

    def test_substitute_template(self) -> None:
        content = "project: {{project_name}}, id: {{project_id}}"
        result = _substitute_template(content, {"project_name": "My App", "project_id": "my-app"})
        assert result == "project: My App, id: my-app"

    def test_substitute_no_match(self) -> None:
        content = "no placeholders here"
        result = _substitute_template(content, {"key": "val"})
        assert result == "no placeholders here"

    def test_copy_template_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.yaml").write_text("name: {{project_name}}")

        dst = tmp_path / "dst"
        _copy_template_dir(src, dst, {"project_name": "Test Project"})

        assert (dst / "file.yaml").read_text() == "name: Test Project"

    def test_copy_template_dir_nested(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        (src / "sub").mkdir(parents=True)
        (src / "sub" / "nested.txt").write_text("id: {{project_id}}")

        dst = tmp_path / "dst"
        _copy_template_dir(src, dst, {"project_id": "my-proj"})

        assert (dst / "sub" / "nested.txt").read_text() == "id: my-proj"


class TestScaffold:
    """Tests for scaffold (git init) flow."""

    @pytest.mark.anyio
    async def test_scaffold_creates_dirs_and_metadata(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=True):
                result = await project_init(config, "my-proj", "scaffold", "python")

        assert "error" not in result
        assert result["project_id"] == "my-proj"
        assert result["source"] == "scaffold"
        assert result["devcontainer"] is True

        assert config.projects_dir is not None
        assert config.repos_dir is not None
        meta_dir = config.projects_dir / "my-proj"
        repo_dir = config.repos_dir / "my-proj"

        assert meta_dir.exists()
        assert (meta_dir / "specs").is_dir()
        assert (meta_dir / "sentinel.yaml").exists()
        assert (meta_dir / "config.yaml").exists()
        assert repo_dir.exists()

    @pytest.mark.anyio
    async def test_scaffold_substitutes_template_vars(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=False):
                result = await project_init(config, "my-proj", "scaffold", "python", project_name="My Cool Project")

        assert "error" not in result
        assert config.projects_dir is not None
        config_content = (config.projects_dir / "my-proj" / "config.yaml").read_text()
        parsed = yaml.safe_load(config_content)
        assert parsed["settings"]["project_name"] == "My Cool Project"

    @pytest.mark.anyio
    async def test_scaffold_defaults_project_name(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=False):
                result = await project_init(config, "my-proj", "scaffold", "python")

        assert "error" not in result
        assert config.projects_dir is not None
        config_content = (config.projects_dir / "my-proj" / "config.yaml").read_text()
        parsed = yaml.safe_load(config_content)
        assert parsed["settings"]["project_name"] == "my-proj"

    @pytest.mark.anyio
    async def test_scaffold_calls_git_init(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=False):
                await project_init(config, "my-proj", "scaffold", "python")

        assert config.repos_dir is not None
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "git"
        assert call_args[1] == "init"
        assert str(config.repos_dir / "my-proj") in call_args[2]


class TestClone:
    """Tests for clone flow."""

    @pytest.mark.anyio
    async def test_clone_calls_git_clone(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=True):
                result = await project_init(
                    config,
                    "my-proj",
                    "clone",
                    "python",
                    git_url="https://github.com/example/repo.git",
                )

        assert "error" not in result
        assert result["source"] == "clone"
        call_args = mock_exec.call_args[0]
        assert call_args[0] == "git"
        assert call_args[1] == "clone"
        assert call_args[2] == "https://github.com/example/repo.git"

    @pytest.mark.anyio
    async def test_clone_failure_returns_error(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=128, stderr=b"fatal: repo not found")
            result = await project_init(
                config,
                "my-proj",
                "clone",
                "python",
                git_url="https://github.com/example/nonexistent.git",
            )

        assert "error" in result
        assert "git clone failed" in result["error"]

    @pytest.mark.anyio
    async def test_clone_failure_no_leftover_dirs(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=128, stderr=b"fatal: error")
            await project_init(
                config,
                "my-proj",
                "clone",
                "python",
                git_url="https://github.com/example/bad.git",
            )

        assert config.projects_dir is not None
        assert not (config.projects_dir / "my-proj").exists()


class TestDevcontainer:
    """Tests for devcontainer fetching."""

    @pytest.mark.anyio
    async def test_devcontainer_success(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=True) as mock_fetch:
                result = await project_init(config, "my-proj", "scaffold", "python")

        assert result["devcontainer"] is True
        mock_fetch.assert_called_once()

    @pytest.mark.anyio
    async def test_devcontainer_failure_non_fatal(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with patch("vizier_mcp.tools.project._fetch_devcontainer", return_value=False):
                result = await project_init(config, "my-proj", "scaffold", "python")

        assert "error" not in result
        assert result["devcontainer"] is False


class TestCleanup:
    """Tests for cleanup on partial failure."""

    @pytest.mark.anyio
    async def test_cleanup_on_exception(self, config: ServerConfig) -> None:
        with patch("vizier_mcp.tools.project.asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = _mock_subprocess(returncode=0)
            with (
                patch("vizier_mcp.tools.project._fetch_devcontainer", side_effect=RuntimeError("boom")),
                pytest.raises(RuntimeError, match="boom"),
            ):
                await project_init(config, "my-proj", "scaffold", "python")

        assert config.projects_dir is not None
        assert config.repos_dir is not None
        # repo_dir was created before the error, should be cleaned up
        assert not (config.repos_dir / "my-proj").exists()


class TestBundledTemplates:
    """Tests that bundled templates exist and are valid."""

    def test_python_templates_exist(self) -> None:
        python_dir = _TEMPLATES_DIR / "python"
        assert python_dir.exists()
        assert (python_dir / "sentinel.yaml").exists()
        assert (python_dir / "config.yaml").exists()

    def test_sentinel_yaml_valid(self) -> None:
        content = (_TEMPLATES_DIR / "python" / "sentinel.yaml").read_text()
        data = yaml.safe_load(content)
        assert "write_set" in data
        assert "command_allowlist" in data
        assert "command_denylist" in data
        assert "role_permissions" in data

    def test_config_yaml_valid(self) -> None:
        content = (_TEMPLATES_DIR / "python" / "config.yaml").read_text()
        data = yaml.safe_load(content)
        assert data["language"] == "python"
        assert "{{project_name}}" in content
