"""Tests for execution tools (bash, git, run_tests)."""

from __future__ import annotations

import subprocess
from pathlib import Path  # noqa: TC003

from vizier.core.tools.domain.exec_tools import create_bash_tool, create_git_tool, create_run_tests_tool


class TestBash:
    def test_simple_command(self) -> None:
        tool = create_bash_tool()
        result = tool.handler(command="echo hello")
        assert "error" not in result
        assert "hello" in result["stdout"]
        assert result["return_code"] == 0

    def test_failing_command(self) -> None:
        tool = create_bash_tool()
        result = tool.handler(command="exit 1")
        assert result["return_code"] == 1

    def test_command_with_cwd(self, tmp_path: Path) -> None:
        tool = create_bash_tool()
        result = tool.handler(command="pwd", cwd=str(tmp_path))
        assert "error" not in result

    def test_timeout(self) -> None:
        tool = create_bash_tool(timeout=1)
        result = tool.handler(command="sleep 10")
        assert "error" in result
        assert "timed out" in result["error"].lower()

    def test_json_schema(self) -> None:
        tool = create_bash_tool()
        assert tool.name == "bash"
        assert "command" in tool.input_schema["properties"]
        assert "command" in tool.input_schema["required"]


class TestGit:
    def test_git_status(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=False)
        tool = create_git_tool(str(tmp_path))
        result = tool.handler(command="status")
        assert "error" not in result

    def test_git_prefix_added(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=False)
        tool = create_git_tool(str(tmp_path))
        result = tool.handler(command="status")
        assert result["return_code"] == 0

    def test_git_with_prefix(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True, check=False)
        tool = create_git_tool(str(tmp_path))
        result = tool.handler(command="git status")
        assert result["return_code"] == 0

    def test_json_schema(self) -> None:
        tool = create_git_tool()
        assert tool.name == "git"
        assert "command" in tool.input_schema["required"]


class TestRunTests:
    def test_passing_tests(self, tmp_path: Path) -> None:
        evidence = tmp_path / "evidence"
        tool = create_run_tests_tool(
            project_root=str(tmp_path),
            evidence_dir=str(evidence),
        )
        result = tool.handler(command="echo PASSED", evidence_file="test.txt")
        assert result["passed"] is True
        assert result["return_code"] == 0
        assert (evidence / "test.txt").exists()
        assert "PASSED" in (evidence / "test.txt").read_text()

    def test_failing_tests(self, tmp_path: Path) -> None:
        tool = create_run_tests_tool(project_root=str(tmp_path))
        result = tool.handler(command="exit 1")
        assert result["passed"] is False
        assert result["return_code"] == 1

    def test_no_evidence_dir(self) -> None:
        tool = create_run_tests_tool()
        result = tool.handler(command="echo ok")
        assert result["evidence_file"] == ""

    def test_timeout(self) -> None:
        tool = create_run_tests_tool(timeout=1)
        result = tool.handler(command="sleep 10")
        assert "error" in result
        assert "timed out" in result["error"].lower()

    def test_json_schema(self) -> None:
        tool = create_run_tests_tool()
        assert tool.name == "run_tests"
        assert "command" in tool.input_schema["properties"]
