"""JIT prompt assembly for EA (D42).

Always-loaded core (~2,500 tokens) plus conditional modules loaded by
deterministic classifier. Saves ~40% on EA input tokens per call.
"""

from __future__ import annotations

from pathlib import Path

from vizier.core.ea.classifier import ClassificationResult, PromptModule
from vizier.core.ea.models import PrioritiesConfig

CORE_PROMPT = """You are the Vizier, the Sultan's Executive Assistant. You manage all projects,
track commitments, and ensure the Sultan's priorities are executed faithfully.

## Your Role
- Single interface between the Sultan and all project Pashas
- Route tasks to the correct project by creating DRAFT specs
- Aggregate progress from all projects via status.json files
- Track real-world commitments with deadlines
- Proactively surface risks, blockers, and overdue items
- Protect the Sultan's attention -- only interrupt for what matters

## Communication Style
- Concise, actionable, and respectful
- Use plain text formatting
- Lead with the most important information
- Suggest next actions when appropriate

## Projects
{projects_section}

## Sultan's Priorities
{priorities_section}

## Active Commitments
{commitments_section}
"""

MODULE_PROMPTS: dict[PromptModule, str] = {
    PromptModule.CHECKIN: """
## Check-in Protocol
You are conducting a structured check-in interview. Ask about:
1. New contacts or relationships worth tracking
2. New commitments or promises made
3. Decisions that affect active projects
4. Blockers or concerns
5. Any other updates

Create relationship and commitment records from the conversation.
Persist check-in results to the ea/ directory.
""",
    PromptModule.FILE_OPS: """
## File Operations
You can help the Sultan check out and check in files:
- **Checkout**: Pull a file from a project repo, send it to the Sultan
- **Checkin**: Receive an edited file back, commit it to the project
- **Relay**: Route an incoming file (photo, document) to a project as spec context

Track checkout state to prevent conflicts. Warn if a checked-out file is stale.
""",
    PromptModule.CALENDAR: """
## Calendar Integration
Cross-reference meetings with commitments and project status.
Prepare briefing materials before meetings.
Alert about upcoming meetings with relevant context.
""",
    PromptModule.CROSS_PROJECT: """
## Cross-Project Coordination
When tasks span multiple projects:
- Create linked DRAFT specs in each relevant project
- Track completion across projects
- Provide unified status summaries
""",
    PromptModule.BUDGET: """
## Budget Management (D33)
Monitor and report on agent costs:
- Show spending vs monthly budget
- Alert at 80% threshold
- At 100%: recommend degrading to cheapest model tier
- At 120%: recommend pausing non-critical work
- Sultan can override any threshold
""",
    PromptModule.BRIEFING: """
## Morning Briefing Format
Structure the briefing as:
1. **Priorities**: Current focus and priority projects
2. **Risks**: Stuck specs, behind-deadline projects
3. **Commitments**: Overdue and upcoming deadlines
4. **Cost Summary**: Spending trend from agent logs
5. **Recommendations**: Suggested actions for the day
""",
    PromptModule.SESSION: """
## Pasha Session
The Sultan wants a deep working session with a project's Pasha.
- Connect them directly to the project orchestrator
- Hold non-urgent updates during the session
- After session ends, read the session summary for continuity
""",
    PromptModule.APPROVAL: """
## Approval Queue
The Sultan is reviewing a pending approval. Present:
- What operation is being requested
- The relevant diff or details
- Risk assessment
- Approve/Reject options
""",
    PromptModule.PROACTIVE: """
## Proactive Behaviors
Check for and surface:
- Overdue commitments (promises past threshold)
- Deadline warnings (project behind vs commitment deadline)
- Completion notices (significant specs reached DONE)
- Risk escalation (STUCK specs, repeated failures)
""",
}


class PromptAssembler:
    """Assembles EA prompts using JIT module loading.

    :param ea_data_dir: Path to ea/ data directory.
    :param projects: List of registered project names.
    """

    def __init__(self, ea_data_dir: str | Path = "", projects: list[str] | None = None) -> None:
        self._ea_data_dir = Path(ea_data_dir) if ea_data_dir else Path("ea")
        self._projects = projects or []

    def assemble(
        self,
        classification: ClassificationResult,
        priorities: PrioritiesConfig | None = None,
        active_commitments: list[str] | None = None,
    ) -> str:
        """Assemble the full prompt from core + JIT modules.

        :param classification: Message classification result.
        :param priorities: Current Sultan priorities.
        :param active_commitments: Summary of active commitments.
        :returns: Assembled prompt string.
        """
        projects_section = self._format_projects()
        priorities_section = self._format_priorities(priorities)
        commitments_section = self._format_commitments(active_commitments)

        prompt = CORE_PROMPT.format(
            projects_section=projects_section,
            priorities_section=priorities_section,
            commitments_section=commitments_section,
        )

        for module in classification.modules:
            if module == PromptModule.CORE:
                continue
            module_prompt = MODULE_PROMPTS.get(module, "")
            if module_prompt:
                prompt += module_prompt

        return prompt

    def _format_projects(self) -> str:
        """Format the project list for the prompt."""
        if not self._projects:
            return "No projects registered."
        return "\n".join(f"- {p}" for p in self._projects)

    def _format_priorities(self, priorities: PrioritiesConfig | None) -> str:
        """Format priorities for the prompt."""
        if not priorities:
            return "No priorities set."

        parts: list[str] = []
        if priorities.current_focus:
            parts.append(f"Current focus: {priorities.current_focus}")
        for p in priorities.priority_order:
            parts.append(f"- {p.project} [{p.urgency}]: {p.reason}")
        if priorities.standing_instructions:
            parts.append("\nStanding instructions:")
            for inst in priorities.standing_instructions:
                parts.append(f"- {inst}")
        return "\n".join(parts) if parts else "No priorities set."

    def _format_commitments(self, commitments: list[str] | None) -> str:
        """Format active commitments summary."""
        if not commitments:
            return "No active commitments."
        return "\n".join(f"- {c}" for c in commitments)

    def load_priorities(self) -> PrioritiesConfig:
        """Load priorities from ea/priorities.yaml.

        :returns: Parsed priorities config.
        """
        priorities_path = self._ea_data_dir / "priorities.yaml"
        if not priorities_path.exists():
            return PrioritiesConfig()

        import yaml

        data = yaml.safe_load(priorities_path.read_text(encoding="utf-8"))
        if not data:
            return PrioritiesConfig()

        return PrioritiesConfig(**data)
