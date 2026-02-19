"""Retrospective AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Retrospective role with:
- Contract B tool set (read_file, glob, grep, read_spec, list_specs, send_message)
- Opus tier model, 50K token budget
- Golden Trace analysis (D57) and process debt register
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.retrospective.prompts import RetrospectivePromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_send_message_tool
from vizier.core.tools.domain import create_glob_tool, create_grep_tool, create_read_file_tool
from vizier.core.tools.state import create_list_specs_tool, create_read_spec_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


def build_retrospective_tools(
    *,
    project_root: str = "",
) -> list[ToolDefinition]:
    """Build the Retrospective tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :returns: List of ToolDefinitions for the Retrospective agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_glob_tool(project_root),
        create_grep_tool(project_root),
        create_read_spec_tool(project_root),
        create_list_specs_tool(project_root),
        create_send_message_tool(project_root),
    ]
    return tools


def create_retrospective_runtime(
    *,
    client: Any,
    project_root: str = "",
    metrics_summary: str = "",
    debt_register: str = "",
    model: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
) -> AgentRuntime:
    """Create a fully configured Retrospective AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param metrics_summary: Current metrics for prompt context.
    :param debt_register: Current process debt register contents.
    :param model: Model identifier. Defaults to Opus.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 50K tokens.
    :param trace: Optional trace logger.
    :returns: Configured AgentRuntime for Retrospective.
    """
    assembler = RetrospectivePromptAssembler(
        metrics_summary=metrics_summary,
        debt_register=debt_register,
    )
    system_prompt = assembler.assemble()

    tools = build_retrospective_tools(project_root=project_root)

    return AgentRuntime(
        client=client,
        model=model or "claude-opus-4-20250514",
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=50000),
        trace=trace,
        agent_role="retrospective",
        spec_id="",
    )
