"""Tests for orchestration tools: delegation, escalation, research re-request, spawn."""

from __future__ import annotations

import json
import os
from pathlib import Path  # noqa: TC003
from typing import Any

from vizier.core.tools.orchestration.delegation_tools import (
    create_delegate_to_architect_tool,
    create_delegate_to_quality_gate_tool,
    create_delegate_to_scout_tool,
    create_delegate_to_worker_tool,
    create_escalate_to_ea_tool,
    create_escalate_to_pasha_tool,
    create_request_more_research_tool,
    create_spawn_agent_tool,
)


def _setup_project(tmp_path: Path) -> str:
    spec_dir = tmp_path / ".vizier" / "specs" / "001-test"
    spec_dir.mkdir(parents=True)
    return str(tmp_path)


class TestDelegationTools:
    def test_delegate_to_scout(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_delegate_to_scout_tool(root)
        result = tool.handler(spec_id="001-test", goal="Research JWT libraries")
        assert "error" not in result
        assert result["role"] == "scout"
        assert result["spawned"] is False

    def test_delegate_to_architect(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_delegate_to_architect_tool(root)
        result = tool.handler(spec_id="001-test", goal="Decompose auth feature")
        assert "error" not in result
        assert result["role"] == "architect"

    def test_delegate_to_worker(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_delegate_to_worker_tool(root)
        result = tool.handler(spec_id="001-test", goal="Implement data model")
        assert "error" not in result
        assert result["role"] == "worker"

    def test_delegate_to_quality_gate(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_delegate_to_quality_gate_tool(root)
        result = tool.handler(spec_id="001-test")
        assert "error" not in result
        assert result["role"] == "quality_gate"

    def test_delegation_writes_assignment(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_delegate_to_worker_tool(root)
        tool.handler(spec_id="001-test", goal="Build it")
        msg_dir = os.path.join(root, ".vizier", "specs", "001-test", "messages")
        files = os.listdir(msg_dir)
        assert len(files) == 1
        with open(os.path.join(msg_dir, files[0]), encoding="utf-8") as f:
            assignment = json.load(f)
        assert assignment["type"] == "TASK_ASSIGNMENT"
        assert assignment["assigned_role"] == "worker"
        assert assignment["goal"] == "Build it"

    def test_delegation_with_spawn_callback(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        spawned: list[tuple[str, str, dict[str, Any]]] = []

        def mock_spawn(role: str, spec_id: str, ctx: dict[str, Any]) -> str:
            spawned.append((role, spec_id, ctx))
            return "pid-123"

        tool = create_delegate_to_scout_tool(root, spawn_callback=mock_spawn)
        result = tool.handler(spec_id="001-test", goal="Research")
        assert result["spawned"] is True
        assert len(spawned) == 1
        assert spawned[0][0] == "scout"

    def test_delegation_no_project_root(self) -> None:
        tool = create_delegate_to_scout_tool()
        result = tool.handler(spec_id="x")
        assert "error" in result

    def test_json_schema_delegate_to_scout(self) -> None:
        tool = create_delegate_to_scout_tool()
        assert tool.name == "delegate_to_scout"
        assert "spec_id" in tool.input_schema["required"]

    def test_json_schema_delegate_to_worker(self) -> None:
        tool = create_delegate_to_worker_tool()
        assert tool.name == "delegate_to_worker"


class TestEscalationTools:
    def test_escalate_to_pasha(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_escalate_to_pasha_tool(root)
        result = tool.handler(spec_id="001-test", reason="Tests keep failing")
        assert "error" not in result
        assert result["target"] == "pasha"
        assert os.path.exists(result["path"])
        with open(result["path"], encoding="utf-8") as f:
            esc = json.load(f)
        assert esc["type"] == "ESCALATION"
        assert esc["severity"] == "medium"

    def test_escalate_to_ea(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_escalate_to_ea_tool(root)
        result = tool.handler(spec_id="001-test", reason="Need human approval", severity="high")
        assert "error" not in result
        assert result["target"] == "ea"
        assert result["severity"] == "high"

    def test_escalation_with_attempted(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_escalate_to_pasha_tool(root)
        attempted = json.dumps(["Tried retry", "Tried different approach"])
        result = tool.handler(spec_id="001-test", reason="Stuck", attempted=attempted)
        assert "error" not in result

    def test_escalation_invalid_severity(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_escalate_to_pasha_tool(root)
        result = tool.handler(spec_id="001-test", reason="x", severity="extreme")
        assert "error" in result
        assert "Invalid severity" in result["error"]

    def test_escalation_no_project_root(self) -> None:
        tool = create_escalate_to_pasha_tool()
        result = tool.handler(spec_id="x", reason="x")
        assert "error" in result

    def test_json_schema_escalate_to_pasha(self) -> None:
        tool = create_escalate_to_pasha_tool()
        assert tool.name == "escalate_to_pasha"
        assert "reason" in tool.input_schema["required"]

    def test_json_schema_escalate_to_ea(self) -> None:
        tool = create_escalate_to_ea_tool()
        assert tool.name == "escalate_to_ea"


class TestRequestMoreResearch:
    def test_request_with_json_array(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_request_more_research_tool(root)
        questions = json.dumps(["What license is PyJWT?", "Any security vulnerabilities?"])
        result = tool.handler(spec_id="001-test", questions=questions)
        assert "error" not in result
        assert result["questions_count"] == 2
        with open(result["path"], encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["questions"]) == 2

    def test_request_with_single_string(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_request_more_research_tool(root)
        result = tool.handler(spec_id="001-test", questions="What alternatives exist?")
        assert "error" not in result
        assert result["questions_count"] == 1

    def test_request_missing_spec(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_request_more_research_tool(root)
        result = tool.handler(spec_id="nonexistent", questions="x")
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_request_no_project_root(self) -> None:
        tool = create_request_more_research_tool()
        result = tool.handler(spec_id="x", questions="x")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_request_more_research_tool()
        assert tool.name == "request_more_research"
        assert "questions" in tool.input_schema["required"]


class TestSpawnAgent:
    def test_spawn_without_callback(self) -> None:
        tool = create_spawn_agent_tool()
        result = tool.handler(role="worker", spec_id="001-test")
        assert result["spawned"] is False
        assert "No spawn callback" in result["reason"]

    def test_spawn_with_callback(self) -> None:
        spawned: list[tuple[str, str]] = []

        def mock_spawn(role: str, spec_id: str, ctx: dict[str, Any]) -> int:
            spawned.append((role, spec_id))
            return 12345

        tool = create_spawn_agent_tool(spawn_callback=mock_spawn)
        result = tool.handler(role="worker", spec_id="001-test")
        assert result["spawned"] is True
        assert "12345" in result["result"]
        assert len(spawned) == 1

    def test_spawn_invalid_role(self) -> None:
        tool = create_spawn_agent_tool()
        result = tool.handler(role="invalid", spec_id="001-test")
        assert "error" in result
        assert "Invalid role" in result["error"]

    def test_spawn_with_context(self) -> None:
        spawned_ctx: list[dict[str, Any]] = []

        def mock_spawn(_r: str, _s: str, ctx: dict[str, Any]) -> None:
            spawned_ctx.append(ctx)

        tool = create_spawn_agent_tool(spawn_callback=mock_spawn)
        ctx = json.dumps({"model": "opus", "budget": 50000})
        result = tool.handler(role="architect", spec_id="001", context=ctx)
        assert result["spawned"] is True
        assert spawned_ctx[0]["model"] == "opus"

    def test_spawn_callback_error(self) -> None:
        def failing_spawn(_r: str, _s: str, _c: dict[str, Any]) -> None:
            raise RuntimeError("Process creation failed")

        tool = create_spawn_agent_tool(spawn_callback=failing_spawn)
        result = tool.handler(role="worker", spec_id="001")
        assert "error" in result
        assert "Process creation failed" in result["error"]

    def test_json_schema(self) -> None:
        tool = create_spawn_agent_tool()
        assert tool.name == "spawn_agent"
        assert "role" in tool.input_schema["required"]
        assert "spec_id" in tool.input_schema["required"]
