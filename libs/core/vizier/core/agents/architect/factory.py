"""Architect AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Architect role with:
- Contract B tool set (read_file, glob, grep, request_more_research, create_spec,
  read_spec, update_spec_status, send_message, ping_supervisor)
- Opus tier model, 80K token budget
- PROPOSE_PLAN with depends_on DAG (D52)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.architect.prompts import ArchitectPromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_ping_supervisor_tool, create_send_message_tool
from vizier.core.tools.domain import create_glob_tool, create_grep_tool, create_read_file_tool
from vizier.core.tools.orchestration import create_request_more_research_tool
from vizier.core.tools.state import create_create_spec_tool, create_read_spec_tool, create_update_spec_status_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


def build_architect_tools(
    *,
    project_root: str = "",
) -> list[ToolDefinition]:
    """Build the Architect tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :returns: List of ToolDefinitions for the Architect agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_glob_tool(project_root),
        create_grep_tool(project_root),
        create_request_more_research_tool(project_root),
        create_create_spec_tool(project_root),
        create_read_spec_tool(project_root),
        create_update_spec_status_tool(project_root),
        create_send_message_tool(project_root),
        create_ping_supervisor_tool(project_root),
    ]
    return tools


def create_architect_runtime(
    *,
    client: Any,
    project_root: str = "",
    spec_id: str = "",
    learnings: str = "",
    architect_guide: str = "",
    model: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
) -> AgentRuntime:
    """Create a fully configured Architect AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param spec_id: Parent spec being decomposed.
    :param learnings: Content from learnings.md for known pitfalls.
    :param architect_guide: Plugin-specific decomposition guidance.
    :param model: Model identifier. Defaults to Opus.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 80K tokens.
    :param trace: Optional trace logger.
    :returns: Configured AgentRuntime for Architect.
    """
    assembler = ArchitectPromptAssembler(learnings=learnings, architect_guide=architect_guide)
    system_prompt = assembler.assemble()

    tools = build_architect_tools(project_root=project_root)

    return AgentRuntime(
        client=client,
        model=model or "claude-opus-4-6",
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=80000),
        trace=trace,
        agent_role="architect",
        spec_id=spec_id,
    )
