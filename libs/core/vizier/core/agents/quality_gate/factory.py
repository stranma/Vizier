"""Quality Gate AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Quality Gate role with:
- Contract B tool set (read_file, glob, grep, bash, run_tests,
  update_spec_status, write_feedback, send_message, ping_supervisor)
- Sonnet tier model (Opus for HIGH complexity, D49)
- Mandatory run_tests before LLM-assisted passes
- Structured QUALITY_VERDICT output (D56)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.quality_gate.prompts import QualityGatePromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_ping_supervisor_tool, create_send_message_tool
from vizier.core.tools.domain import (
    create_bash_tool,
    create_glob_tool,
    create_grep_tool,
    create_read_file_tool,
    create_run_tests_tool,
)
from vizier.core.tools.state import create_update_spec_status_tool, create_write_feedback_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


def build_quality_gate_tools(
    *,
    project_root: str = "",
    evidence_dir: str = "",
) -> list[ToolDefinition]:
    """Build the Quality Gate tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :param evidence_dir: Directory for storing evidence files.
    :returns: List of ToolDefinitions for the Quality Gate agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_glob_tool(project_root),
        create_grep_tool(project_root),
        create_bash_tool(project_root),
        create_run_tests_tool(project_root, evidence_dir=evidence_dir),
        create_update_spec_status_tool(project_root),
        create_write_feedback_tool(project_root),
        create_send_message_tool(project_root),
        create_ping_supervisor_tool(project_root),
    ]
    return tools


def _resolve_qg_model(complexity: str) -> str:
    """Resolve QG model based on spec complexity (D49).

    HIGH complexity specs get Opus for semantic review passes.

    :param complexity: Spec complexity (LOW/MEDIUM/HIGH).
    :returns: Model identifier string.
    """
    if complexity == "HIGH":
        return "claude-opus-4-20250514"
    return "claude-sonnet-4-20250514"


def create_quality_gate_runtime(
    *,
    client: Any,
    project_root: str = "",
    spec_id: str = "",
    acceptance_criteria: str = "",
    quality_guide: str = "",
    complexity: str = "MEDIUM",
    evidence_dir: str = "",
    model: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
) -> AgentRuntime:
    """Create a fully configured Quality Gate AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param spec_id: Spec being validated.
    :param acceptance_criteria: Spec acceptance criteria to validate against.
    :param quality_guide: Plugin-specific quality guidance.
    :param complexity: Spec complexity (D49: HIGH -> Opus semantic review).
    :param evidence_dir: Directory for storing evidence files.
    :param model: Model override. If empty, resolved from complexity.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 30K tokens.
    :param trace: Optional trace logger.
    :returns: Configured AgentRuntime for Quality Gate.
    """
    assembler = QualityGatePromptAssembler(
        acceptance_criteria=acceptance_criteria,
        quality_guide=quality_guide,
    )
    system_prompt = assembler.assemble()

    tools = build_quality_gate_tools(
        project_root=project_root,
        evidence_dir=evidence_dir,
    )

    resolved_model = model or _resolve_qg_model(complexity)

    return AgentRuntime(
        client=client,
        model=resolved_model,
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=30000),
        trace=trace,
        agent_role="quality_gate",
        spec_id=spec_id,
    )
