"""Pasha AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Pasha orchestrator role with:
- Contract B tool set (delegation, state, communication, report_progress, spawn_agent)
- Mode-specific prompt assembly
- Budget and trace configuration
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from vizier.core.agents.pasha.prompts import PashaPromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_report_progress_tool, create_send_message_tool
from vizier.core.tools.orchestration import (
    create_delegate_to_architect_tool,
    create_delegate_to_quality_gate_tool,
    create_delegate_to_scout_tool,
    create_delegate_to_worker_tool,
    create_escalate_to_ea_tool,
    create_spawn_agent_tool,
)
from vizier.core.tools.state import create_list_specs_tool, create_read_spec_tool, create_update_spec_status_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine

SpawnCallback = Callable[[str, str, dict[str, Any]], Any]


def build_pasha_tools(
    *,
    project_root: str = "",
    spawn_callback: SpawnCallback | None = None,
) -> list[ToolDefinition]:
    """Build the Pasha tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :param spawn_callback: Optional callback for spawning agent subprocesses.
    :returns: List of ToolDefinitions for the Pasha agent.
    """
    tools: list[ToolDefinition] = [
        create_delegate_to_scout_tool(project_root, spawn_callback),
        create_delegate_to_architect_tool(project_root, spawn_callback),
        create_delegate_to_worker_tool(project_root, spawn_callback),
        create_delegate_to_quality_gate_tool(project_root, spawn_callback),
        create_escalate_to_ea_tool(project_root),
        create_spawn_agent_tool(spawn_callback),
        create_report_progress_tool(project_root),
        create_read_spec_tool(project_root),
        create_update_spec_status_tool(project_root),
        create_list_specs_tool(project_root),
        create_send_message_tool(project_root),
    ]
    return tools


def create_pasha_runtime(
    *,
    client: Any,
    project_root: str = "",
    project_name: str = "",
    project_context: str = "",
    model: str = "",
    mode: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
    spawn_callback: SpawnCallback | None = None,
) -> AgentRuntime:
    """Create a fully configured Pasha AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param project_name: Name of the project this Pasha manages.
    :param project_context: Additional project context (constitution, learnings).
    :param model: Model identifier. Defaults to Opus.
    :param mode: Prompt mode ("session", "reconciliation", or empty for default).
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 30K tokens.
    :param trace: Optional trace logger.
    :param spawn_callback: Optional callback for spawning agent subprocesses.
    :returns: Configured AgentRuntime for Pasha.
    """
    assembler = PashaPromptAssembler(project_name=project_name, project_context=project_context)
    system_prompt = assembler.assemble(mode)

    tools = build_pasha_tools(project_root=project_root, spawn_callback=spawn_callback)

    return AgentRuntime(
        client=client,
        model=model or "claude-opus-4-20250514",
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=30000),
        trace=trace,
        agent_role="pasha",
        spec_id="",
    )
