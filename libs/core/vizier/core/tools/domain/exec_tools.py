"""Execution tools: bash, git, run_tests."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from vizier.core.runtime.types import ToolDefinition


def create_bash_tool(
    project_root: str = "",
    timeout: int = 120,
) -> ToolDefinition:
    """Create the bash tool for running shell commands.

    :param project_root: Default working directory.
    :param timeout: Default command timeout in seconds.
    :returns: ToolDefinition for bash.
    """

    def handler(*, command: str, cwd: str = "") -> dict[str, Any]:
        work_dir = cwd or project_root or None
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
            )
            return {
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s: {command[:100]}"}
        except Exception as e:
            return {"error": f"Command failed: {e}"}

    return ToolDefinition(
        name="bash",
        description="Execute a shell command. Returns stdout, stderr, and return code.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory (default: project root)"},
            },
            "required": ["command"],
        },
        handler=handler,
    )


def create_git_tool(project_root: str = "") -> ToolDefinition:
    """Create the git tool for safe git operations.

    :param project_root: Git repository root.
    :returns: ToolDefinition for git.
    """

    def handler(*, command: str) -> dict[str, Any]:
        if not command.startswith("git "):
            command = f"git {command}"
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=project_root or None,
            )
            return {
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Git command timed out: {command[:100]}"}
        except Exception as e:
            return {"error": f"Git command failed: {e}"}

    return ToolDefinition(
        name="git",
        description="Execute a git command. Sentinel enforces safe/dangerous classification.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git command (e.g. 'status', 'diff', 'log --oneline -10')",
                },
            },
            "required": ["command"],
        },
        handler=handler,
    )


def create_run_tests_tool(
    project_root: str = "",
    evidence_dir: str = "",
    timeout: int = 300,
) -> ToolDefinition:
    """Create the run_tests tool that captures output to evidence files.

    :param project_root: Project root for test execution.
    :param evidence_dir: Directory to write test evidence files.
    :param timeout: Test timeout in seconds.
    :returns: ToolDefinition for run_tests.
    """

    def handler(*, command: str = "pytest", evidence_file: str = "test_output.txt") -> dict[str, Any]:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=project_root or None,
            )
            output = result.stdout + "\n" + result.stderr

            if evidence_dir:
                evidence_path = os.path.join(evidence_dir, evidence_file)
                os.makedirs(evidence_dir, exist_ok=True)
                with open(evidence_path, "w", encoding="utf-8") as f:
                    f.write(output)

            passed = result.returncode == 0
            return {
                "passed": passed,
                "return_code": result.returncode,
                "stdout": result.stdout[:10000],
                "stderr": result.stderr[:5000],
                "evidence_file": evidence_file if evidence_dir else "",
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Tests timed out after {timeout}s"}
        except Exception as e:
            return {"error": f"Test execution failed: {e}"}

    return ToolDefinition(
        name="run_tests",
        description="Run test suite and capture output to evidence file. Returns pass/fail and output.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Test command to run (default: 'pytest')",
                },
                "evidence_file": {
                    "type": "string",
                    "description": "Filename for evidence output (default: 'test_output.txt')",
                },
            },
        },
        handler=handler,
    )
