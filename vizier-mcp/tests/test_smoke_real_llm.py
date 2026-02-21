"""Phase 5 smoke test: real LLM round-trip validating the tool contract.

This test exercises the full spec lifecycle via call_tool AND validates
that Sentinel's Haiku evaluator works with real API calls for ambiguous
commands. Marked with @pytest.mark.integration so it's skipped in CI
(requires ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest

from vizier_mcp.config import ServerConfig
from vizier_mcp.server import create_server
from vizier_mcp.tools.sentinel import run_command_checked as _run_command_checked

if TYPE_CHECKING:
    from pathlib import Path

    from fastmcp import FastMCP


pytestmark = [pytest.mark.anyio, pytest.mark.integration]

SKIP_REASON = "ANTHROPIC_API_KEY not set"
HAS_API_KEY = bool(os.environ.get("ANTHROPIC_API_KEY"))


def _data(result: object) -> dict[str, Any]:
    """Extract the structured dict from a FastMCP ToolResult."""
    return result.structured_content  # type: ignore[union-attr]


@pytest.fixture
def smoke_root(tmp_path: Path) -> Path:
    """Create a project directory with a Sentinel policy for smoke testing."""
    project_dir = tmp_path / "projects" / "smoke-project"
    specs_dir = project_dir / "specs"
    specs_dir.mkdir(parents=True)

    sentinel_yaml = project_dir / "sentinel.yaml"
    sentinel_yaml.write_text(
        "write_set:\n"
        '  - "src/**/*.py"\n'
        '  - "tests/**/*.py"\n'
        "command_allowlist:\n"
        '  - "echo"\n'
        '  - "pytest"\n'
        '  - "ruff"\n'
        "command_denylist:\n"
        '  - pattern: "rm\\\\s+-rf"\n'
        '    reason: "Destructive command"\n'
        '  - "sudo"\n'
        "role_permissions:\n"
        "  worker:\n"
        "    can_write: true\n"
        "    can_bash: true\n"
        "    can_read: true\n"
        "  quality_gate:\n"
        "    can_write: false\n"
        "    can_bash: true\n"
        "    can_read: true\n"
    )
    return tmp_path


@pytest.fixture
def smoke_config(smoke_root: Path) -> ServerConfig:
    return ServerConfig(vizier_root=smoke_root)


@pytest.fixture
def server(smoke_config: ServerConfig) -> FastMCP:
    return create_server(smoke_config)


@pytest.mark.skipif(not HAS_API_KEY, reason=SKIP_REASON)
class TestRealLLMSmokeTest:
    """Full lifecycle smoke test with real Haiku API call."""

    async def test_full_lifecycle_with_real_haiku(self, server: FastMCP, smoke_config: ServerConfig) -> None:
        """Vizier creates spec, Pasha promotes, Worker runs command (Haiku eval), QG accepts."""
        project_id = "smoke-project"

        # Step 1: Vizier creates a spec
        create_result = await server.call_tool(
            "spec_create",
            {
                "project_id": project_id,
                "title": "Smoke Test Spec",
                "description": "Validate the MCP tool contract with a real LLM call",
                "complexity": "LOW",
            },
        )
        data = _data(create_result)
        assert "spec_id" in data, f"spec_create failed: {data}"
        spec_id = data["spec_id"]

        # Step 2: Pasha promotes DRAFT -> READY
        result = await server.call_tool(
            "spec_transition",
            {"project_id": project_id, "spec_id": spec_id, "new_status": "READY", "agent_role": "pasha"},
        )
        assert _data(result)["success"] is True

        # Step 3: Worker claims READY -> IN_PROGRESS
        result = await server.call_tool(
            "spec_transition",
            {"project_id": project_id, "spec_id": spec_id, "new_status": "IN_PROGRESS", "agent_role": "worker"},
        )
        assert _data(result)["success"] is True

        # Step 4: Worker runs an allowlisted command (no Haiku needed)
        result = await server.call_tool(
            "run_command_checked",
            {"project_id": project_id, "command": "echo hello from worker", "agent_role": "worker"},
        )
        cmd_data = _data(result)
        assert cmd_data["allowed"] is True
        assert cmd_data["exit_code"] == 0
        assert "hello from worker" in cmd_data["stdout"]

        # Step 5: Worker runs an ambiguous command - triggers REAL Haiku call
        # The MCP server wrapper doesn't pass llm_callable, so ambiguous commands
        # fail-closed via the server. We call the tool function directly with a
        # real Anthropic LLM callable to validate the Haiku round-trip.
        import anthropic

        client = anthropic.AsyncAnthropic()

        async def real_llm(model: str, prompt: str, max_tokens: int = 10) -> str:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text  # type: ignore[union-attr]

        ambiguous_result = await _run_command_checked(
            smoke_config,
            project_id,
            "ls -la",  # safe but ambiguous (not in allowlist or denylist)
            "worker",
            llm_callable=real_llm,
        )
        # Haiku should ALLOW "ls -la" as a safe read-only command
        assert "allowed" in ambiguous_result
        if ambiguous_result["allowed"]:
            assert ambiguous_result["exit_code"] == 0
        # If Haiku denies it, that's also valid behavior -- the key is no crash

        # Step 6: Worker transitions to REVIEW
        result = await server.call_tool(
            "spec_transition",
            {"project_id": project_id, "spec_id": spec_id, "new_status": "REVIEW", "agent_role": "worker"},
        )
        assert _data(result)["success"] is True

        # Step 7: QG reads the spec
        result = await server.call_tool(
            "spec_read",
            {"project_id": project_id, "spec_id": spec_id},
        )
        read_data = _data(result)
        assert read_data["metadata"]["status"] == "REVIEW"

        # Step 8: QG writes feedback (ACCEPT)
        result = await server.call_tool(
            "spec_write_feedback",
            {
                "project_id": project_id,
                "spec_id": spec_id,
                "verdict": "ACCEPT",
                "feedback": "All criteria met. Smoke test passed.",
            },
        )
        assert "path" in _data(result)

        # Step 9: QG transitions REVIEW -> DONE
        result = await server.call_tool(
            "spec_transition",
            {"project_id": project_id, "spec_id": spec_id, "new_status": "DONE", "agent_role": "quality_gate"},
        )
        assert _data(result)["success"] is True

        # Step 10: Verify final state
        result = await server.call_tool(
            "spec_read",
            {"project_id": project_id, "spec_id": spec_id},
        )
        final = _data(result)
        assert final["metadata"]["status"] == "DONE"

    async def test_denylisted_command_blocked(self, server: FastMCP) -> None:
        """Verify a denylisted command is blocked without any LLM call."""
        result = await server.call_tool(
            "run_command_checked",
            {"project_id": "smoke-project", "command": "sudo rm -rf /", "agent_role": "worker"},
        )
        data = _data(result)
        assert data["allowed"] is False
        assert "reason" in data

    async def test_sentinel_check_write(self, server: FastMCP) -> None:
        """Verify write-set enforcement works end-to-end."""
        # Allowed path
        result = await server.call_tool(
            "sentinel_check_write",
            {"project_id": "smoke-project", "file_path": "src/main.py", "agent_role": "worker"},
        )
        assert _data(result)["allowed"] is True

        # Denied path
        result = await server.call_tool(
            "sentinel_check_write",
            {"project_id": "smoke-project", "file_path": "/etc/passwd", "agent_role": "worker"},
        )
        assert _data(result)["allowed"] is False
