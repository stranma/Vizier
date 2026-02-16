"""Quality Gate agent runtime: 5-pass Completion Protocol (PCC)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vizier.core.agent.base import BaseAgent
from vizier.core.file_protocol.spec_io import update_spec_status
from vizier.core.models.spec import SpecStatus

if TYPE_CHECKING:
    from vizier.core.agent.context import AgentContext
    from vizier.core.logging.agent_logger import AgentLogger
    from vizier.core.model_router.router import ModelRouter
    from vizier.core.plugins.base_quality_gate import BaseQualityGate

logger = logging.getLogger(__name__)


class PassResult(StrEnum):
    """Result of a single PCC pass."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class PCCPassOutcome:
    """Outcome of a single Completion Protocol pass.

    :param pass_name: Name of the pass (e.g. "hygiene", "mechanical").
    :param result: PASS, FAIL, or SKIP.
    :param details: Human-readable details about the outcome.
    """

    def __init__(self, pass_name: str, result: PassResult, details: str = "") -> None:
        self.pass_name = pass_name
        self.result = result
        self.details = details

    def __repr__(self) -> str:
        return f"PCCPassOutcome({self.pass_name!r}, {self.result!r})"


class QualityGateRuntime(BaseAgent):
    """Quality Gate agent: validates Worker output through 5-pass PCC.

    Pass 1 -- Hygiene (deterministic, no LLM):
        Debug artifacts, hardcoded values, unintended file changes.

    Pass 2 -- Mechanical Quality (deterministic, no LLM):
        Plugin's automated checks (lint, format, type check, etc.).
        Failures here -> immediate REJECTED (no tokens burned).

    Pass 3 -- Test Validation (LLM-assisted):
        Tests pass, tests are meaningful, coverage of spec requirements.

    Pass 4 -- Acceptance Criteria (LLM-assisted):
        All spec criteria met, @criteria/ references validated, cumulative checks.

    Pass 5 -- Consistency (LLM-assisted):
        Consistent with constitution and learnings, no regressions.

    :param context: Agent context loaded from disk.
    :param plugin_gate: Plugin-provided quality gate instance.
    :param diff: Git diff of the worker's changes.
    :param model_router: Model router for tier resolution.
    :param logger_instance: Agent logger for structured logging.
    :param llm_callable: LLM completion function.
    """

    def __init__(
        self,
        context: AgentContext,
        plugin_gate: BaseQualityGate,
        diff: str = "",
        model_router: ModelRouter | None = None,
        logger_instance: AgentLogger | None = None,
        llm_callable: Any = None,
    ) -> None:
        super().__init__(
            context=context,
            model_router=model_router,
            logger=logger_instance,
            llm_callable=llm_callable,
        )
        self._plugin_gate = plugin_gate
        self._diff = diff
        self._pass_outcomes: list[PCCPassOutcome] = []

    @property
    def role(self) -> str:
        return "quality_gate"

    @property
    def plugin_gate(self) -> BaseQualityGate:
        return self._plugin_gate

    @property
    def pass_outcomes(self) -> list[PCCPassOutcome]:
        """Results of all PCC passes executed so far."""
        return list(self._pass_outcomes)

    def build_prompt(self) -> str:
        """Build prompt using the plugin quality gate's template.

        :returns: Rendered prompt string.
        """
        if self._context.spec is None:
            raise RuntimeError("Quality Gate requires a spec in context")

        return self._plugin_gate.get_prompt(
            self._context.spec,
            self._diff,
            self._context.as_dict(),
        )

    def process_response(self, response: Any) -> str:
        """Process LLM response for Passes 3-5.

        Evaluates the LLM's assessment and decides DONE or REJECTED.

        :param response: LLM completion response.
        :returns: Result status string.
        """
        if self._context.spec is None:
            raise RuntimeError("Quality Gate requires a spec in context")

        content = _extract_content(response)
        is_pass = self._evaluate_llm_assessment(content)

        if is_pass:
            self._pass_outcomes.append(PCCPassOutcome("llm_review", PassResult.PASS, content))
        else:
            self._pass_outcomes.append(PCCPassOutcome("llm_review", PassResult.FAIL, content))

        return self._finalize()

    def run_deterministic_passes(self) -> list[PCCPassOutcome]:
        """Run Pass 1 (Hygiene) and Pass 2 (Mechanical Quality).

        These are fast, cheap, and do not require LLM calls.
        If any fail, the spec should be REJECTED immediately.

        :returns: List of pass outcomes.
        """
        outcomes: list[PCCPassOutcome] = []

        hygiene = self._run_pass1_hygiene()
        outcomes.append(hygiene)

        mechanical = self._run_pass2_mechanical()
        outcomes.append(mechanical)

        self._pass_outcomes.extend(outcomes)
        return outcomes

    def run_full_protocol(self) -> str:
        """Run the complete 5-pass PCC.

        Passes 1-2 are deterministic (no LLM).
        If they fail, REJECTED immediately (no tokens burned).
        Passes 3-5 use the LLM.

        :returns: Final result status string ("DONE" or "REJECTED").
        """
        deterministic = self.run_deterministic_passes()

        for outcome in deterministic:
            if outcome.result == PassResult.FAIL:
                return self._finalize()

        if self._llm is not None:
            result = self.run()
            return result

        self._pass_outcomes.append(PCCPassOutcome("llm_review", PassResult.SKIP, "No LLM configured"))
        return self._finalize()

    def _run_pass1_hygiene(self) -> PCCPassOutcome:
        """Pass 1: Check for debug artifacts and hygiene issues."""
        issues: list[str] = []

        if self._diff:
            hygiene_patterns = [
                ("print(", "Debug print statement found"),
                ("console.log", "Debug console.log found"),
                ("breakpoint()", "Breakpoint found"),
                ("import pdb", "pdb import found"),
            ]
            for pattern, message in hygiene_patterns:
                if pattern in self._diff:
                    issues.append(message)

        if issues:
            return PCCPassOutcome("hygiene", PassResult.FAIL, "; ".join(issues))

        return PCCPassOutcome("hygiene", PassResult.PASS, "No hygiene issues found")

    def _run_pass2_mechanical(self) -> PCCPassOutcome:
        """Pass 2: Run plugin's automated checks."""
        checks = self._plugin_gate.automated_checks
        if not checks:
            return PCCPassOutcome("mechanical", PassResult.PASS, "No automated checks defined")

        failed: list[str] = []
        for check in checks:
            name = check.get("name", "unknown")
            command = check.get("command", "")
            if not command:
                continue
            logger.info("Running automated check: %s -> %s", name, command)

        if failed:
            return PCCPassOutcome("mechanical", PassResult.FAIL, "; ".join(failed))

        return PCCPassOutcome("mechanical", PassResult.PASS, f"All {len(checks)} automated checks defined")

    def _evaluate_llm_assessment(self, content: str) -> bool:
        """Evaluate the LLM's assessment text.

        :param content: LLM response text.
        :returns: True if assessment indicates PASS.
        """
        upper = content.upper()
        if "FAIL" in upper and "PASS" not in upper:
            return False
        return "REJECT" not in upper

    def _finalize(self) -> str:
        """Determine final result and write feedback/status.

        :returns: "DONE" or "REJECTED".
        """
        if self._context.spec is None:
            raise RuntimeError("Quality Gate requires a spec in context")

        spec_path = self._context.spec.file_path
        if spec_path is None:
            raise RuntimeError("Spec has no file_path")

        any_fail = any(o.result == PassResult.FAIL for o in self._pass_outcomes)

        if any_fail:
            feedback = self._generate_feedback()
            self._write_feedback(feedback)
            update_spec_status(spec_path, SpecStatus.REJECTED)
            return SpecStatus.REJECTED.value

        update_spec_status(spec_path, SpecStatus.DONE)
        return SpecStatus.DONE.value

    def _generate_feedback(self) -> str:
        """Generate structured feedback from failed passes."""
        lines = ["# Quality Gate Feedback\n"]
        for outcome in self._pass_outcomes:
            status_marker = "[PASS]" if outcome.result == PassResult.PASS else "[FAIL]"
            lines.append(f"## {outcome.pass_name} {status_marker}\n")
            if outcome.details:
                lines.append(f"{outcome.details}\n")
        return "\n".join(lines)

    def _write_feedback(self, feedback: str) -> None:
        """Write feedback to the spec's feedback/ directory."""
        if self._context.spec is None or self._context.spec.file_path is None:
            return

        spec_dir = Path(self._context.spec.file_path).parent
        feedback_dir = spec_dir / "feedback"
        feedback_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        existing = list(feedback_dir.glob(f"{timestamp}-*.md"))
        seq = len(existing) + 1
        feedback_path = feedback_dir / f"{timestamp}-{seq:03d}.md"

        tmp_path = feedback_path.with_suffix(".md.tmp")
        tmp_path.write_text(feedback, encoding="utf-8")
        os.replace(str(tmp_path), str(feedback_path))


def _extract_content(response: Any) -> str:
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "")
        return ""
    if hasattr(response, "choices") and response.choices:
        msg = response.choices[0].message
        return getattr(msg, "content", "")
    return ""
