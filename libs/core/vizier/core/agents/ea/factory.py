"""EA AgentRuntime factory: assembles tools, prompt, and runtime (D47).

Creates a fully configured AgentRuntime for the EA role with:
- Contract B tool set (read_file, create_spec, read_spec, list_specs, send_message, send_briefing)
- JIT prompt assembly (D42)
- Project capability summary (D59)
- Budget and trace configuration
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.ea.capability_summary import (
    ProjectCapability,
    format_capabilities_for_prompt,
)
from vizier.core.agents.ea.prompts import EAPromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_send_briefing_tool, create_send_message_tool
from vizier.core.tools.domain import create_read_file_tool
from vizier.core.tools.state import create_create_spec_tool, create_list_specs_tool, create_read_spec_tool

if TYPE_CHECKING:
    from collections.abc import Callable

    from vizier.core.sentinel.engine import SentinelEngine


def build_ea_tools(
    *,
    project_root: str = "",
    send_callback: Callable[[str], None] | None = None,
) -> list[ToolDefinition]:
    """Build the EA tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :param send_callback: Optional callback for briefing delivery (Telegram).
    :returns: List of ToolDefinitions for the EA agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_create_spec_tool(project_root),
        create_read_spec_tool(project_root),
        create_list_specs_tool(project_root),
        create_send_message_tool(project_root),
        create_send_briefing_tool(send_callback=send_callback),
    ]
    return tools


def create_ea_runtime(
    *,
    client: Any,
    project_root: str = "",
    model: str = "",
    capabilities: list[ProjectCapability] | None = None,
    priorities: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
    send_callback: Callable[[str], None] | None = None,
    initial_message: str = "",
) -> AgentRuntime:
    """Create a fully configured EA AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param model: Model identifier. Defaults to Opus via ModelRouter.
    :param capabilities: Project capability summaries for prompt injection.
    :param priorities: Sultan's current priorities text.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 50K tokens.
    :param trace: Optional trace logger.
    :param send_callback: Optional Telegram delivery callback.
    :param initial_message: Message to classify for JIT prompt assembly.
    :returns: Configured AgentRuntime for EA.
    """
    cap_text = format_capabilities_for_prompt(capabilities or [])
    assembler = EAPromptAssembler(project_summary=cap_text, priorities=priorities)

    system_prompt = assembler.assemble(initial_message) if initial_message else assembler.core_prompt

    tools = build_ea_tools(project_root=project_root, send_callback=send_callback)

    return AgentRuntime(
        client=client,
        model=model or "claude-opus-4-20250514",
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=50000),
        trace=trace,
        agent_role="ea",
        spec_id="",
    )
