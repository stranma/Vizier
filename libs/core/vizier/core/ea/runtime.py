"""EA (Executive Assistant) runtime -- Sultan-facing agent.

Monolithic, Opus-tier agent that handles all Sultan communication.
Uses JIT prompt assembly (D42) for efficient context window usage.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from vizier.core.ea.budget import BudgetEnforcer, BudgetStatus
from vizier.core.ea.classifier import ClassificationResult, MessageCategory, MessageClassifier
from vizier.core.ea.conversation_log import ConversationLog, ConversationTurn
from vizier.core.ea.models import (
    BudgetConfig,
    CheckinRecord,
    CheckoutRecord,
    FocusMode,
)
from vizier.core.ea.prompt_assembly import PromptAssembler
from vizier.core.ea.tracking import CommitmentTracker, RelationshipTracker
from vizier.core.file_protocol.spec_io import create_spec, list_specs

logger = logging.getLogger(__name__)


class EARuntime:
    """Executive Assistant runtime -- Sultan's single interface to the system.

    :param ea_data_dir: Path to ea/ data directory.
    :param reports_dir: Path to cross-project reports/ directory.
    :param projects: Dict mapping project name -> project root path.
    :param llm_callable: LLM function for generating responses.
    :param budget_config: Optional budget enforcement configuration.
    """

    def __init__(
        self,
        ea_data_dir: str | Path = "ea",
        reports_dir: str | Path = "reports",
        projects: dict[str, str] | None = None,
        llm_callable: Any | None = None,
        budget_config: BudgetConfig | None = None,
    ) -> None:
        self._ea_dir = Path(ea_data_dir)
        self._reports_dir = Path(reports_dir)
        self._projects = projects or {}
        self._llm_callable = llm_callable

        self._classifier = MessageClassifier()
        self._assembler = PromptAssembler(
            ea_data_dir=self._ea_dir,
            projects=list(self._projects.keys()),
        )
        self._budget = BudgetEnforcer(budget_config)
        self._focus = FocusMode()

        commitments_dir = self._ea_dir / "commitments"
        relationships_dir = self._ea_dir / "relationships"
        self._commitments = CommitmentTracker(commitments_dir)
        self._relationships = RelationshipTracker(relationships_dir)

        self._ea_dir.mkdir(parents=True, exist_ok=True)
        sessions_dir = self._ea_dir / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)
        self._conversation_log = ConversationLog(sessions_dir)

    @property
    def classifier(self) -> MessageClassifier:
        """Return the message classifier."""
        return self._classifier

    @property
    def focus_mode(self) -> FocusMode:
        """Return current focus mode state."""
        return self._focus

    @property
    def commitments(self) -> CommitmentTracker:
        """Return the commitment tracker."""
        return self._commitments

    @property
    def relationships(self) -> RelationshipTracker:
        """Return the relationship tracker."""
        return self._relationships

    def handle_message(self, message: str) -> str:
        """Process an incoming Sultan message and return a response.

        :param message: The Sultan's message text.
        :returns: EA's response text.
        """
        classification = self._classifier.classify(message)

        if (
            self._focus.active
            and not self._focus.is_expired
            and classification.category not in (MessageCategory.CONTROL, MessageCategory.APPROVAL)
        ):
            self._focus.held_messages.append(message)
            return "Focus mode active. Message held for later."

        if classification.category == MessageCategory.FOCUS:
            response = self._handle_focus(classification)
        elif classification.category == MessageCategory.STATUS:
            response = self._handle_status(classification)
        elif classification.category == MessageCategory.BUDGET:
            response = self._handle_budget(classification)
        elif classification.category == MessageCategory.PRIORITIES:
            response = self._handle_priorities()
        elif classification.category == MessageCategory.DELEGATION:
            response = self._handle_delegation(message, classification)
        elif classification.category == MessageCategory.QUICK_QUERY:
            response = self._handle_quick_query(classification)
        elif classification.category == MessageCategory.CONTROL:
            response = self._handle_control(message, classification)
        else:
            response = self._handle_general(message, classification)

        self._conversation_log.append(
            ConversationTurn(role="user", content=message, category=classification.category.value)
        )
        self._conversation_log.append(
            ConversationTurn(role="assistant", content=response, category=classification.category.value)
        )
        return response

    def _handle_focus(self, classification: ClassificationResult) -> str:
        """Enter or exit focus mode."""
        duration_str = classification.extra.get("duration_hours", "2")
        try:
            duration = float(duration_str)
        except ValueError:
            duration = 2.0

        self._focus = FocusMode(
            active=True,
            started_at=datetime.utcnow(),
            duration_hours=duration,
        )
        return f"Focus mode activated for {duration}h. Only emergencies will get through."

    def _handle_status(self, classification: ClassificationResult) -> str:
        """Read status.json files and compile a status report."""
        project = classification.project
        statuses: list[dict[str, Any]] = []

        if project and project in self._projects:
            status = self._read_project_status(project)
            if status:
                statuses.append(status)
        else:
            for proj_name in self._projects:
                status = self._read_project_status(proj_name)
                if status:
                    statuses.append(status)

        if not statuses:
            if project:
                return f"No status available for project '{project}'."
            return "No project status data available."

        return self._format_status_report(statuses)

    def _handle_budget(self, classification: ClassificationResult) -> str:
        """Show budget status from agent logs."""
        project = classification.project
        if project and project in self._projects:
            log_path = self._reports_dir / project / "agent-log.jsonl"
            status = self._budget.compute_status(log_path)
            return self._format_budget_report(project, status)

        total_spent = 0.0
        total_calls = 0
        project_reports: list[str] = []
        for proj_name in self._projects:
            log_path = self._reports_dir / proj_name / "agent-log.jsonl"
            status = self._budget.compute_status(log_path)
            total_spent += status.total_spent_usd
            total_calls += status.agent_calls
            if status.agent_calls > 0:
                project_reports.append(f"  {proj_name}: ${status.total_spent_usd:.2f} ({status.agent_calls} calls)")

        lines = [f"Total spending: ${total_spent:.2f} / ${self._budget.config.monthly_budget_usd:.2f}"]
        if project_reports:
            lines.append("By project:")
            lines.extend(project_reports)
        return "\n".join(lines)

    def _handle_priorities(self) -> str:
        """Show current priorities from priorities.yaml."""
        priorities = self._assembler.load_priorities()
        if not priorities.current_focus and not priorities.priority_order:
            return "No priorities configured. Edit ea/priorities.yaml to set them."

        lines: list[str] = []
        if priorities.current_focus:
            lines.append(f"Current focus: {priorities.current_focus}")
        for p in priorities.priority_order:
            lines.append(f"- {p.project} [{p.urgency}]: {p.reason}")
        if priorities.standing_instructions:
            lines.append("\nStanding instructions:")
            for inst in priorities.standing_instructions:
                lines.append(f"  - {inst}")
        return "\n".join(lines)

    def _handle_delegation(self, message: str, classification: ClassificationResult) -> str:
        """Create a DRAFT spec in the target project."""
        project = classification.project
        if not project:
            if len(self._projects) == 1:
                project = next(iter(self._projects))
            else:
                return "Which project should I delegate this to? Please specify a project name."

        if project not in self._projects:
            return f"Unknown project '{project}'. Registered projects: {', '.join(self._projects.keys())}"

        project_root = Path(self._projects[project])
        spec_id = self._next_spec_id(project_root)
        spec = create_spec(
            project_root=str(project_root),
            spec_id=spec_id,
            content=message,
        )
        return f"Task delegated to {project}. Created spec {spec.frontmatter.id} (DRAFT)."

    def _next_spec_id(self, project_root: Path) -> str:
        """Generate the next sequential spec ID for a project."""
        existing = list_specs(str(project_root))
        if not existing:
            return "001"
        max_num = 0
        for spec in existing:
            try:
                num = int(spec.frontmatter.id.split("-")[0])
                max_num = max(max_num, num)
            except (ValueError, IndexError):
                pass
        return f"{max_num + 1:03d}"

    def _handle_quick_query(self, classification: ClassificationResult) -> str:
        """Route a quick query to the project."""
        project = classification.project
        query = classification.extra.get("query", "")
        if not project:
            return "Please specify a project: /ask <project-name> <question>"
        if project not in self._projects:
            return f"Unknown project '{project}'."
        if not query:
            return f"What would you like to ask about {project}?"
        return f"Routing query to {project}: {query}"

    def _handle_control(self, message: str, classification: ClassificationResult) -> str:
        """Handle control commands (stop, cancel, pause)."""
        project = classification.project
        if not project:
            return "Please specify which project to apply this control to."
        if project not in self._projects:
            return f"Unknown project '{project}'."
        return f"Control command received for {project}. Processing: {message}"

    def _handle_general(self, message: str, classification: ClassificationResult) -> str:
        """Handle general messages using LLM with conversation history."""
        if self._llm_callable is None:
            return "Message received. LLM not configured for general responses."

        priorities = self._assembler.load_priorities()
        active = [
            f"{c.description} (due: {c.deadline.strftime('%Y-%m-%d') if c.deadline else 'no deadline'})"
            for c in self._commitments.list_active()
        ]
        prompt = self._assembler.assemble(classification, priorities, active)

        history = self._conversation_log.recent(10)
        messages: list[dict[str, str]] = [{"role": "system", "content": prompt}]
        for turn in history:
            messages.append({"role": turn.role, "content": turn.content})
        messages.append({"role": "user", "content": message})

        try:
            response = self._llm_callable(
                model="anthropic/claude-opus-4-6",
                messages=messages,
            )
            return response.choices[0].message.content
        except Exception:
            logger.exception("EA LLM call failed")
            return "I understood your message but encountered an error generating a response."

    def _read_project_status(self, project: str) -> dict[str, Any] | None:
        """Read status.json for a project."""
        status_path = self._reports_dir / project / "status.json"
        if not status_path.exists():
            return None
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _format_status_report(self, statuses: list[dict[str, Any]]) -> str:
        """Format status data into a human-readable report."""
        lines: list[str] = []
        for status in statuses:
            name = status.get("project", "unknown")
            lines.append(f"Project: {name}")
            if "total_specs" in status:
                lines.append(f"  Specs: {status['total_specs']} total")
            if "done_count" in status:
                lines.append(f"  Done: {status['done_count']}")
            if "in_progress_count" in status:
                lines.append(f"  In progress: {status['in_progress_count']}")
            if "stuck_count" in status:
                lines.append(f"  Stuck: {status['stuck_count']}")
            if "cycle" in status:
                lines.append(f"  Cycle: {status['cycle']}")
            lines.append("")
        return "\n".join(lines).strip()

    def _format_budget_report(self, project: str, status: BudgetStatus) -> str:
        """Format a single project's budget report."""
        lines = [
            f"Budget for {project}:",
            f"  Spent: ${status.total_spent_usd:.2f} / ${status.monthly_budget_usd:.2f}",
            f"  Usage: {status.usage_ratio:.0%}",
            f"  Status: {status.threshold}",
            f"  Agent calls: {status.agent_calls}",
        ]
        if status.recommended_tier:
            lines.append(f"  Recommended tier: {status.recommended_tier}")
        return "\n".join(lines)

    def get_escalations(self) -> list[dict[str, Any]]:
        """Check all projects for escalation files.

        :returns: List of escalation data dicts.
        """
        escalations: list[dict[str, Any]] = []
        for project_name in self._projects:
            esc_dir = self._reports_dir / project_name / "escalations"
            if not esc_dir.exists():
                continue
            for f in sorted(esc_dir.glob("*.md")):
                escalations.append(
                    {
                        "project": project_name,
                        "file": f.name,
                        "content": f.read_text(encoding="utf-8"),
                    }
                )
        return escalations

    def generate_briefing(self) -> str:
        """Generate a morning briefing for the Sultan.

        :returns: Formatted briefing text.
        """
        priorities = self._assembler.load_priorities()
        sections: list[str] = ["Morning Briefing", "=" * 40]

        if priorities.current_focus:
            sections.append(f"\nFocus: {priorities.current_focus}")

        overdue = self._commitments.list_overdue()
        active = self._commitments.list_active()
        if overdue:
            sections.append(f"\nOverdue commitments ({len(overdue)}):")
            for c in overdue:
                sections.append(f"  - {c.description} (promised to {c.promised_to})")
        if active:
            sections.append(f"\nActive commitments ({len(active)}):")
            for c in active:
                deadline_str = c.deadline.strftime("%Y-%m-%d") if c.deadline else "no deadline"
                sections.append(f"  - {c.description} (due: {deadline_str})")

        escalations = self.get_escalations()
        if escalations:
            sections.append(f"\nEscalations ({len(escalations)}):")
            for esc in escalations:
                sections.append(f"  - [{esc['project']}] {esc['file']}")

        total_spent = 0.0
        for proj_name in self._projects:
            log_path = self._reports_dir / proj_name / "agent-log.jsonl"
            status = self._budget.compute_status(log_path)
            total_spent += status.total_spent_usd
        sections.append(f"\nCost: ${total_spent:.2f} / ${self._budget.config.monthly_budget_usd:.2f}")

        return "\n".join(sections)

    def release_focus(self) -> list[str]:
        """Exit focus mode and return held messages.

        :returns: List of messages held during focus mode.
        """
        held = list(self._focus.held_messages)
        self._focus = FocusMode()
        return held

    def record_checkin(self, record: CheckinRecord) -> Path:
        """Persist a check-in record to ea/checkins/.

        :param record: The check-in record to save.
        :returns: Path to the written file.
        """
        import os

        import yaml

        checkins_dir = self._ea_dir / "checkins"
        checkins_dir.mkdir(parents=True, exist_ok=True)
        path = checkins_dir / f"{record.id}.yaml"
        tmp_path = path.with_suffix(".yaml.tmp")
        data = record.model_dump(mode="json")
        tmp_path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
        os.replace(str(tmp_path), str(path))
        return path

    def track_checkout(self, checkout: CheckoutRecord) -> Path:
        """Record a file checkout in ea/checkouts.yaml.

        :param checkout: The checkout record.
        :returns: Path to the checkouts file.
        """
        import os

        import yaml

        checkouts_path = self._ea_dir / "checkouts.yaml"
        existing: list[dict[str, Any]] = []
        if checkouts_path.exists():
            data = yaml.safe_load(checkouts_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                existing = data

        existing.append(checkout.model_dump(mode="json"))
        tmp_path = checkouts_path.with_suffix(".yaml.tmp")
        tmp_path.write_text(yaml.dump(existing, default_flow_style=False), encoding="utf-8")
        os.replace(str(tmp_path), str(checkouts_path))
        return checkouts_path
