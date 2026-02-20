"""Scout AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Scout role with:
- Contract B tool set (read_file, bash, update_spec_status, send_message)
- Sonnet tier model, 20K token budget
- Structured RESEARCH_REPORT output
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.scout.prompts import ScoutPromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_send_message_tool
from vizier.core.tools.domain import create_bash_tool, create_read_file_tool
from vizier.core.tools.state import create_update_spec_status_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


def build_scout_tools(
    *,
    project_root: str = "",
) -> list[ToolDefinition]:
    """Build the Scout tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :returns: List of ToolDefinitions for the Scout agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_bash_tool(project_root, timeout=60),
        create_update_spec_status_tool(project_root),
        create_send_message_tool(project_root),
    ]
    return tools


def create_scout_runtime(
    *,
    client: Any,
    project_root: str = "",
    spec_id: str = "",
    plugin_guide: str = "",
    model: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
) -> AgentRuntime:
    """Create a fully configured Scout AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param spec_id: Spec being researched.
    :param plugin_guide: Plugin-specific research guidance.
    :param model: Model identifier. Defaults to Sonnet.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 20K tokens.
    :param trace: Optional trace logger.
    :returns: Configured AgentRuntime for Scout.
    """
    assembler = ScoutPromptAssembler(plugin_guide=plugin_guide)
    system_prompt = assembler.assemble()

    tools = build_scout_tools(project_root=project_root)

    return AgentRuntime(
        client=client,
        model=model or "claude-sonnet-4-6",
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=20000),
        trace=trace,
        agent_role="scout",
        spec_id=spec_id,
    )
