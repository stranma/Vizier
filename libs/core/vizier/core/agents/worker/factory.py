"""Worker AgentRuntime factory: assembles tools, prompt, and runtime.

Creates a fully configured AgentRuntime for the Worker role with:
- Contract B full domain tool set + orchestration + state + communication
- Sonnet tier model (Opus on HIGH complexity or retry 3+), 100K token budget
- Glob-pattern write-set enforcement (D55)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vizier.core.agents.worker.prompts import WorkerPromptAssembler
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger  # noqa: TC001
from vizier.core.runtime.types import ToolDefinition  # noqa: TC001
from vizier.core.tools.communication import create_ping_supervisor_tool, create_send_message_tool
from vizier.core.tools.domain import (
    WriteSetChecker,
    create_bash_tool,
    create_edit_file_tool,
    create_git_tool,
    create_glob_tool,
    create_grep_tool,
    create_read_file_tool,
    create_run_tests_tool,
    create_write_file_tool,
)
from vizier.core.tools.orchestration import create_escalate_to_pasha_tool
from vizier.core.tools.state import create_update_spec_status_tool, create_write_feedback_tool

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


def build_worker_tools(
    *,
    project_root: str = "",
    evidence_dir: str = "",
    write_set: WriteSetChecker | None = None,
) -> list[ToolDefinition]:
    """Build the Worker tool set per Contract B.

    :param project_root: Root directory for file and spec operations.
    :param evidence_dir: Directory for test evidence output.
    :param write_set: Write-set checker for boundary enforcement (D55).
    :returns: List of ToolDefinitions for the Worker agent.
    """
    tools: list[ToolDefinition] = [
        create_read_file_tool(project_root),
        create_write_file_tool(project_root, write_set=write_set),
        create_edit_file_tool(project_root, write_set=write_set),
        create_bash_tool(project_root),
        create_glob_tool(project_root),
        create_grep_tool(project_root),
        create_git_tool(project_root),
        create_run_tests_tool(project_root, evidence_dir=evidence_dir),
        create_escalate_to_pasha_tool(project_root),
        create_update_spec_status_tool(project_root),
        create_write_feedback_tool(project_root),
        create_send_message_tool(project_root),
        create_ping_supervisor_tool(project_root),
    ]
    return tools


def _resolve_model(complexity: str, retry_count: int) -> str:
    """Resolve model based on complexity and retry count.

    :param complexity: Spec complexity (LOW/MEDIUM/HIGH).
    :param retry_count: Current retry attempt number.
    :returns: Model identifier string.
    """
    if complexity == "HIGH" or retry_count >= 3:
        return "claude-opus-4-6"
    return "claude-sonnet-4-6"


def create_worker_runtime(
    *,
    client: Any,
    project_root: str = "",
    spec_id: str = "",
    goal: str = "",
    constraints: str = "",
    acceptance_criteria: str = "",
    write_set_patterns: list[str] | None = None,
    complexity: str = "MEDIUM",
    retry_count: int = 0,
    learnings: str = "",
    worker_guide: str = "",
    evidence_dir: str = "",
    model: str = "",
    sentinel: SentinelEngine | None = None,
    budget: BudgetConfig | None = None,
    trace: TraceLogger | None = None,
) -> AgentRuntime:
    """Create a fully configured Worker AgentRuntime.

    :param client: Anthropic client (or mock) with messages.create().
    :param project_root: Root directory for file and spec operations.
    :param spec_id: Spec being executed.
    :param goal: Spec goal text.
    :param constraints: Spec constraints text.
    :param acceptance_criteria: Spec acceptance criteria text.
    :param write_set_patterns: Glob patterns for write-set enforcement (D55).
    :param complexity: Spec complexity (LOW/MEDIUM/HIGH).
    :param retry_count: Current retry attempt number (drives model escalation).
    :param learnings: Relevant entries from learnings.md.
    :param worker_guide: Plugin-specific worker guidance.
    :param evidence_dir: Directory for test evidence output.
    :param model: Model override. If empty, resolved from complexity/retry.
    :param sentinel: Optional Sentinel engine for security.
    :param budget: Budget config. Defaults to 100K tokens.
    :param trace: Optional trace logger.
    :returns: Configured AgentRuntime for Worker.
    """
    write_set = WriteSetChecker(write_set_patterns or [], project_root) if write_set_patterns else None
    write_set_str = ", ".join(write_set_patterns) if write_set_patterns else "(unrestricted)"

    assembler = WorkerPromptAssembler(
        goal=goal,
        constraints=constraints,
        acceptance_criteria=acceptance_criteria,
        write_set=write_set_str,
        complexity=complexity,
        learnings=learnings,
        worker_guide=worker_guide,
    )
    system_prompt = assembler.assemble()

    tools = build_worker_tools(
        project_root=project_root,
        evidence_dir=evidence_dir,
        write_set=write_set,
    )

    resolved_model = model or _resolve_model(complexity, retry_count)

    return AgentRuntime(
        client=client,
        model=resolved_model,
        system_prompt=system_prompt,
        tools=tools,
        sentinel=sentinel,
        budget=budget or BudgetConfig(max_tokens=100000),
        trace=trace,
        agent_role="worker",
        spec_id=spec_id,
    )
