"""Retrospective agent runtime: meta-improvement through failure analysis."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vizier.core.agent.base import BaseAgent
from vizier.core.retrospective.analysis import RetrospectiveAnalysis

logger = logging.getLogger(__name__)


class RetrospectiveRuntime(BaseAgent):
    """Retrospective agent that analyzes failures and writes learnings/proposals.

    Triggered after cycle completion or STUCK events. Reads rejection history,
    stuck specs, and agent logs. Updates learnings.md directly and writes
    proposals to .vizier/proposals/ for Sultan approval.

    :param context: Agent context loaded from disk.
    :param llm_callable: LLM completion function.
    :param model_router: Optional model router.
    :param logger_instance: Optional agent logger.
    :param agent_log_path: Path to agent-log.jsonl for cost analysis.
    """

    def __init__(
        self,
        context: Any,
        llm_callable: Any = None,
        model_router: Any = None,
        logger_instance: Any = None,
        agent_log_path: str = "",
    ) -> None:
        super().__init__(
            context=context,
            model_router=model_router,
            logger=logger_instance,
            llm_callable=llm_callable,
        )
        self._agent_log_path = agent_log_path
        self._analysis = RetrospectiveAnalysis(context.project_root, agent_log_path)
        self._learnings_added: list[str] = []
        self._proposals_written: list[str] = []

    @property
    def role(self) -> str:
        return "retrospective"

    @property
    def learnings_added(self) -> list[str]:
        """Learnings appended during this run."""
        return list(self._learnings_added)

    @property
    def proposals_written(self) -> list[str]:
        """Proposal file paths written during this run."""
        return list(self._proposals_written)

    def build_prompt(self) -> str:
        """Build the Retrospective prompt with analysis report and project context.

        :returns: Rendered prompt string.
        """
        report = self._analysis.generate_analysis_report()

        return (
            "# Retrospective: Analyze and Improve\n\n"
            "You are the Retrospective agent. Your job is to analyze project failures "
            "and inefficiencies, then produce actionable improvements.\n\n"
            "## Current Analysis\n\n"
            f"{report}\n\n"
            "## Current Learnings\n\n"
            f"{self.context.learnings or 'No learnings recorded yet.'}\n\n"
            "## Your Tasks\n\n"
            "1. **Identify root causes** of the failure patterns above\n"
            "2. **Write learnings** - concise, actionable insights to append to learnings.md\n"
            "3. **Write proposals** - for structural changes that require Sultan approval\n\n"
            "## Output Format\n\n"
            "### Learnings\n"
            "For each learning, use this format:\n"
            "LEARNING: <one-line actionable insight>\n\n"
            "### Proposals\n"
            "For each proposal, use this format:\n"
            "PROPOSAL: <title>\n"
            "TYPE: prompt_change | criteria_change | process_change\n"
            "DESCRIPTION: <detailed description of the proposed change>\n"
            "RATIONALE: <why this change would help, based on evidence>\n\n"
            "## Rules\n"
            "- Learnings must be specific and actionable (not vague advice)\n"
            "- Reference specific spec IDs and failure types\n"
            "- Proposals ALWAYS require Sultan approval - never auto-approve\n"
            "- Base recommendations on evidence, not assumptions\n"
            "- If no improvements are needed, say so explicitly\n"
        )

    def process_response(self, response: Any) -> str:
        """Parse LLM response and apply learnings/proposals.

        :param response: LLM completion response.
        :returns: Summary of actions taken.
        """
        content = _extract_content(response)

        learnings = _parse_learnings(content)
        if learnings:
            self._append_learnings(learnings)
            self._learnings_added.extend(learnings)

        proposals = _parse_proposals(content)
        for title, body in proposals:
            path = self._write_proposal(title, body)
            self._proposals_written.append(path)

        summary_parts: list[str] = []
        if learnings:
            summary_parts.append(f"{len(learnings)} learning(s) added")
        if proposals:
            summary_parts.append(f"{len(proposals)} proposal(s) written")
        if not summary_parts:
            summary_parts.append("no changes needed")

        return f"RETROSPECTIVE: {', '.join(summary_parts)}"

    def run_analysis(self) -> str:
        """Run the full retrospective flow: analyze -> LLM -> apply.

        :returns: Summary string.
        """
        return self.run()

    def _append_learnings(self, learnings: list[str]) -> None:
        """Append new learnings to learnings.md.

        :param learnings: List of learning strings to append.
        """
        learnings_path = Path(self.context.project_root) / ".vizier" / "learnings.md"
        learnings_path.parent.mkdir(parents=True, exist_ok=True)

        existing = ""
        if learnings_path.exists():
            existing = learnings_path.read_text(encoding="utf-8")

        date = datetime.utcnow().strftime("%Y-%m-%d")
        new_section = f"\n\n## Retrospective ({date})\n\n"
        new_section += "\n".join(f"- {learning}" for learning in learnings)
        new_section += "\n"

        updated = existing.rstrip() + new_section
        tmp = learnings_path.with_suffix(".md.tmp")
        tmp.write_text(updated, encoding="utf-8")
        os.replace(str(tmp), str(learnings_path))

        logger.info("Appended %d learnings to learnings.md", len(learnings))

    def _write_proposal(self, title: str, body: str) -> str:
        """Write a proposal file for Sultan review.

        :param title: Proposal title.
        :param body: Proposal body content.
        :returns: Path to the written proposal file.
        """
        proposals_dir = Path(self.context.project_root) / ".vizier" / "proposals"
        proposals_dir.mkdir(parents=True, exist_ok=True)

        date = datetime.utcnow().strftime("%Y-%m-%d")
        safe_title = title.lower().replace(" ", "-")[:50]
        filename = f"{date}-{safe_title}.md"
        path = proposals_dir / filename

        content = f"# Proposal: {title}\n\n**Date:** {date}\n**Status:** PENDING (requires Sultan approval)\n\n{body}\n"

        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))

        logger.info("Wrote proposal: %s", filename)
        return str(path)


def _extract_content(response: Any) -> str:
    """Extract text content from an LLM response object.

    :param response: LLM completion response (dict or SimpleNamespace).
    :returns: The message content string.
    """
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""

    if hasattr(response, "choices") and response.choices:
        msg = response.choices[0].message
        if hasattr(msg, "content"):
            return msg.content or ""
    return ""


def _parse_learnings(content: str) -> list[str]:
    """Parse LEARNING: lines from LLM response.

    :param content: LLM response text.
    :returns: List of learning strings.
    """
    learnings: list[str] = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("LEARNING:"):
            learning = stripped[len("LEARNING:") :].strip()
            if learning:
                learnings.append(learning)
    return learnings


def _parse_proposals(content: str) -> list[tuple[str, str]]:
    """Parse PROPOSAL: blocks from LLM response.

    :param content: LLM response text.
    :returns: List of (title, body) tuples.
    """
    proposals: list[tuple[str, str]] = []
    lines = content.split("\n")
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.upper().startswith("PROPOSAL:"):
            title = stripped[len("PROPOSAL:") :].strip()
            body_lines: list[str] = []
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if next_line.upper().startswith("PROPOSAL:") or next_line.upper().startswith("LEARNING:"):
                    break
                body_lines.append(lines[i])
                i += 1
            body = "\n".join(body_lines).strip()
            if title:
                proposals.append((title, body))
        else:
            i += 1

    return proposals
