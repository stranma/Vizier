"""Orchestration tools: delegation, escalation, research re-request, agent spawning."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from vizier.core.models.messages import (
    Escalation,
    EscalationSeverity,
    TaskAssignment,
)
from vizier.core.runtime.types import ToolDefinition

SpawnCallback = Callable[[str, str, dict[str, Any]], Any]
"""Callable(role, spec_id, context) -> spawn result."""


def create_delegate_to_scout_tool(
    project_root: str = "",
    spawn_callback: SpawnCallback | None = None,
) -> ToolDefinition:
    """Create the delegate_to_scout tool.

    :param project_root: Project root for message storage.
    :param spawn_callback: Optional callback to spawn the Scout agent subprocess.
    :returns: ToolDefinition for delegate_to_scout.
    """
    return _make_delegation_tool(
        role="scout",
        description="Delegate a spec to Scout for research. Writes a TASK_ASSIGNMENT and optionally spawns the agent.",
        project_root=project_root,
        spawn_callback=spawn_callback,
    )


def create_delegate_to_architect_tool(
    project_root: str = "",
    spawn_callback: SpawnCallback | None = None,
) -> ToolDefinition:
    """Create the delegate_to_architect tool.

    :param project_root: Project root for message storage.
    :param spawn_callback: Optional callback to spawn the Architect agent subprocess.
    :returns: ToolDefinition for delegate_to_architect.
    """
    return _make_delegation_tool(
        role="architect",
        description="Delegate a spec to Architect for decomposition. Writes a TASK_ASSIGNMENT and optionally spawns the agent.",
        project_root=project_root,
        spawn_callback=spawn_callback,
    )


def create_delegate_to_worker_tool(
    project_root: str = "",
    spawn_callback: SpawnCallback | None = None,
) -> ToolDefinition:
    """Create the delegate_to_worker tool.

    :param project_root: Project root for message storage.
    :param spawn_callback: Optional callback to spawn the Worker agent subprocess.
    :returns: ToolDefinition for delegate_to_worker.
    """
    return _make_delegation_tool(
        role="worker",
        description="Delegate a spec to Worker for implementation. Writes a TASK_ASSIGNMENT and optionally spawns the agent.",
        project_root=project_root,
        spawn_callback=spawn_callback,
    )


def create_delegate_to_quality_gate_tool(
    project_root: str = "",
    spawn_callback: SpawnCallback | None = None,
) -> ToolDefinition:
    """Create the delegate_to_quality_gate tool.

    :param project_root: Project root for message storage.
    :param spawn_callback: Optional callback to spawn the QG agent subprocess.
    :returns: ToolDefinition for delegate_to_quality_gate.
    """
    return _make_delegation_tool(
        role="quality_gate",
        description="Delegate a spec to Quality Gate for review. Writes a TASK_ASSIGNMENT and optionally spawns the agent.",
        project_root=project_root,
        spawn_callback=spawn_callback,
    )


def create_escalate_to_pasha_tool(project_root: str = "") -> ToolDefinition:
    """Create the escalate_to_pasha tool.

    :param project_root: Project root for message storage.
    :returns: ToolDefinition for escalate_to_pasha.
    """
    return _make_escalation_tool(
        target="pasha",
        description="Escalate a problem to Pasha (project orchestrator). Writes an ESCALATION message.",
        project_root=project_root,
    )


def create_escalate_to_ea_tool(project_root: str = "") -> ToolDefinition:
    """Create the escalate_to_ea tool.

    :param project_root: Project root for message storage.
    :returns: ToolDefinition for escalate_to_ea.
    """
    return _make_escalation_tool(
        target="ea",
        description="Escalate a problem to EA (Executive Assistant). Writes an ESCALATION message.",
        project_root=project_root,
    )


def create_request_more_research_tool(project_root: str = "") -> ToolDefinition:
    """Create the request_more_research tool (D48).

    Architect sends Scout back for additional research by writing research
    questions to the spec directory.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for request_more_research.
    """

    def handler(*, spec_id: str, questions: str) -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            q_list = json.loads(questions) if questions.startswith("[") else [questions]
        except json.JSONDecodeError:
            q_list = [questions]

        spec_dir = os.path.join(project_root, ".vizier", "specs", spec_id)
        if not os.path.isdir(spec_dir):
            return {"error": f"Spec directory not found: {spec_id}"}

        try:
            filepath = os.path.join(spec_dir, "research_questions.json")
            ts = datetime.now(UTC).isoformat()
            data = {"spec_id": spec_id, "questions": q_list, "requested_at": ts, "requested_by": "architect"}
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return {
                "spec_id": spec_id,
                "questions_count": len(q_list),
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write research questions: {e}"}

    return ToolDefinition(
        name="request_more_research",
        description=(
            "Request additional research from Scout (D48). Writes research questions "
            "to the spec directory. The Architect uses this when Scout's initial "
            "research is insufficient."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier"},
                "questions": {
                    "type": "string",
                    "description": "Research questions (JSON array of strings, or a single question string)",
                },
            },
            "required": ["spec_id", "questions"],
        },
        handler=handler,
    )


def create_spawn_agent_tool(
    spawn_callback: SpawnCallback | None = None,
) -> ToolDefinition:
    """Create the spawn_agent tool.

    :param spawn_callback: Callback to actually spawn the agent subprocess.
    :returns: ToolDefinition for spawn_agent.
    """

    def handler(*, role: str, spec_id: str, context: str = "{}") -> dict[str, Any]:
        valid_roles = {"scout", "architect", "worker", "quality_gate", "retrospective"}
        if role not in valid_roles:
            return {"error": f"Invalid role '{role}'. Valid: {sorted(valid_roles)}"}
        try:
            ctx = json.loads(context) if context != "{}" else {}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid context JSON: {e}"}

        if spawn_callback is not None:
            try:
                result = spawn_callback(role, spec_id, ctx)
                return {
                    "role": role,
                    "spec_id": spec_id,
                    "spawned": True,
                    "result": str(result) if result is not None else "",
                }
            except Exception as e:
                return {"error": f"Failed to spawn {role}: {e}"}

        return {
            "role": role,
            "spec_id": spec_id,
            "spawned": False,
            "reason": "No spawn callback configured",
        }

    return ToolDefinition(
        name="spawn_agent",
        description="Spawn an agent subprocess for a specific role and spec. Used by Pasha to start agents.",
        input_schema={
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "Agent role: scout, architect, worker, quality_gate, retrospective",
                },
                "spec_id": {"type": "string", "description": "Spec identifier for the agent to work on"},
                "context": {
                    "type": "string",
                    "description": "JSON string of additional context for the agent",
                    "default": "{}",
                },
            },
            "required": ["role", "spec_id"],
        },
        handler=handler,
    )


def _make_delegation_tool(
    role: str,
    description: str,
    project_root: str,
    spawn_callback: SpawnCallback | None,
) -> ToolDefinition:
    """Factory for delegation tools that write TASK_ASSIGNMENT + optionally spawn."""

    def handler(*, spec_id: str, goal: str = "", budget_tokens: int = 100000) -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}

        assignment = TaskAssignment(
            spec_id=spec_id,
            goal=goal or f"Process spec {spec_id} as {role}",
            constraints=[],
            budget_tokens=budget_tokens,
            allowed_tools=[],
            assigned_role=role,
        )

        msg_dir = os.path.join(project_root, ".vizier", "specs", spec_id, "messages")
        try:
            os.makedirs(msg_dir, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            filename = f"{ts}-TASK_ASSIGNMENT-{role}.json"
            filepath = os.path.join(msg_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(assignment.model_dump(mode="json"), f, indent=2, default=str)
        except Exception as e:
            return {"error": f"Failed to write assignment: {e}"}

        result: dict[str, Any] = {
            "spec_id": spec_id,
            "role": role,
            "assignment_file": filename,
        }

        if spawn_callback is not None:
            try:
                spawn_callback(role, spec_id, {"goal": goal, "budget_tokens": budget_tokens})
                result["spawned"] = True
            except Exception as e:
                result["spawned"] = False
                result["spawn_error"] = str(e)
        else:
            result["spawned"] = False

        return result

    return ToolDefinition(
        name=f"delegate_to_{role}",
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier to delegate"},
                "goal": {
                    "type": "string",
                    "description": f"Goal for the {role} agent",
                    "default": "",
                },
                "budget_tokens": {
                    "type": "integer",
                    "description": "Token budget for this delegation",
                    "default": 100000,
                },
            },
            "required": ["spec_id"],
        },
        handler=handler,
    )


def _make_escalation_tool(
    target: str,
    description: str,
    project_root: str,
) -> ToolDefinition:
    """Factory for escalation tools that write ESCALATION messages."""

    def handler(
        *,
        spec_id: str,
        reason: str,
        severity: str = "medium",
        attempted: str = "[]",
    ) -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            sev = EscalationSeverity(severity)
        except ValueError:
            valid = [s.value for s in EscalationSeverity]
            return {"error": f"Invalid severity '{severity}'. Valid: {valid}"}
        try:
            attempted_list = json.loads(attempted) if attempted != "[]" else []
        except json.JSONDecodeError:
            attempted_list = [attempted]

        escalation = Escalation(
            spec_id=spec_id,
            severity=sev,
            reason=reason,
            attempted=attempted_list,
            needed_from_supervisor=f"Escalated to {target} for resolution",
        )

        msg_dir = os.path.join(project_root, ".vizier", "specs", spec_id, "messages")
        try:
            os.makedirs(msg_dir, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            filename = f"{ts}-ESCALATION-to-{target}.json"
            filepath = os.path.join(msg_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(escalation.model_dump(mode="json"), f, indent=2, default=str)
            return {
                "spec_id": spec_id,
                "target": target,
                "severity": severity,
                "file": filename,
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write escalation: {e}"}

    return ToolDefinition(
        name=f"escalate_to_{target}",
        description=description,
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier"},
                "reason": {"type": "string", "description": "Reason for escalation"},
                "severity": {
                    "type": "string",
                    "description": "Severity level: low, medium, high, critical",
                    "default": "medium",
                },
                "attempted": {
                    "type": "string",
                    "description": "JSON array of attempted solutions",
                    "default": "[]",
                },
            },
            "required": ["spec_id", "reason"],
        },
        handler=handler,
    )
