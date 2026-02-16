"""Scout agent runtime: prior art research on DRAFT specs."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from vizier.core.agent.base import BaseAgent
from vizier.core.file_protocol.spec_io import update_spec_status
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin  # noqa: TC001
from vizier.core.scout.classifier import ScoutClassifier, ScoutDecision
from vizier.core.scout.report import ResearchReport, write_report
from vizier.core.scout.sources import (
    GitHubSearchSource,
    NpmSearchSource,
    PyPISearchSource,
    SearchResult,
    search_all,
)

logger = logging.getLogger(__name__)


class ScoutRuntime(BaseAgent):
    """Scout agent that researches prior art before Architect decomposition.

    Classifies specs deterministically to decide if research is worthwhile,
    searches external sources (GitHub, PyPI, npm), then writes a research.md
    report and transitions the spec to SCOUTED.

    :param context: Agent context loaded from disk.
    :param plugin: The project's plugin instance.
    :param llm_callable: LLM completion function.
    :param model_router: Optional model router.
    :param logger_instance: Optional agent logger.
    :param tool_executor: Optional ToolExecutor for gh CLI calls.
    """

    def __init__(
        self,
        context: Any,
        plugin: BasePlugin,
        llm_callable: Any = None,
        model_router: Any = None,
        logger_instance: Any = None,
        tool_executor: Any = None,
    ) -> None:
        super().__init__(
            context=context,
            model_router=model_router,
            logger=logger_instance,
            llm_callable=llm_callable,
        )
        self._plugin = plugin
        self._tool_executor = tool_executor
        self._classifier = ScoutClassifier()
        self._report: ResearchReport | None = None

    @property
    def role(self) -> str:
        return "scout"

    @property
    def report(self) -> ResearchReport | None:
        """The research report produced during scouting."""
        return self._report

    def build_prompt(self) -> str:
        """Build the Scout's prompt asking LLM to generate search queries.

        :returns: Rendered prompt string.
        :raises RuntimeError: If no spec is loaded in context.
        """
        if not self.context.spec:
            raise RuntimeError("Scout requires a spec to research")

        spec = self.context.spec
        scout_guide = self._plugin.get_scout_guide()

        return (
            f"# Scout: Research Prior Art\n\n"
            f"You are the Scout agent. Your job is to identify search queries that will "
            f"find existing libraries, packages, tools, or SaaS solutions relevant to this task.\n\n"
            f"## Task\n\n"
            f"**Spec ID:** {spec.frontmatter.id}\n"
            f"**Plugin:** {spec.frontmatter.plugin}\n\n"
            f"### Description\n{spec.content}\n\n"
            f"## Plugin Research Guide\n{scout_guide or 'No specific research guide.'}\n\n"
            f"## Instructions\n\n"
            f"Generate 3-5 search queries that would find:\n"
            f"1. Existing libraries or packages that solve this problem\n"
            f"2. GitHub repositories with similar implementations\n"
            f"3. SaaS or hosted solutions\n\n"
            f"Output one query per line, prefixed with '- '. Example:\n"
            f"- python authentication library JWT\n"
            f"- oauth2 server implementation github\n\n"
            f"After the queries, provide a one-sentence summary of what you're looking for.\n"
            f"Prefix the summary line with 'SUMMARY: '.\n"
        )

    def process_response(self, response: Any) -> str:
        """Parse LLM response for search queries, run searches, write report.

        :param response: LLM completion response.
        :returns: "SCOUTED" on success.
        """
        content = _extract_content(response)
        queries = _parse_queries(content)
        summary = _parse_summary(content)

        sources = self._build_sources()
        results = search_all(queries, sources) if queries else []

        self._report = ResearchReport(
            spec_id=self.context.spec.frontmatter.id if self.context.spec else "unknown",
            decision=ScoutDecision.RESEARCH,
            summary=summary or "Research completed via external search.",
            recommendation=_recommend(results),
            solutions=results,
            queries=queries,
        )

        self._write_and_transition()
        return "SCOUTED"

    def scout(self) -> ResearchReport:
        """Run the full scout flow: classify, research if needed, write report.

        :returns: The research report.
        :raises RuntimeError: If no spec is loaded.
        """
        if not self.context.spec:
            raise RuntimeError("Scout requires a spec to research")

        decision = self._classifier.classify(self.context.spec)
        spec_id = self.context.spec.frontmatter.id

        if decision == ScoutDecision.SKIP:
            logger.info("Scout skipping research for spec %s (classified as SKIP)", spec_id)
            self._report = ResearchReport(
                spec_id=spec_id,
                decision=ScoutDecision.SKIP,
                summary="No external research needed for this task type.",
                recommendation="BUILD_FROM_SCRATCH",
            )
            self._write_and_transition()
            return self._report

        logger.info("Scout researching prior art for spec %s", spec_id)

        if self._llm is not None:
            self.run()
        else:
            self._report = ResearchReport(
                spec_id=spec_id,
                decision=ScoutDecision.RESEARCH,
                summary="No LLM available for query generation.",
                recommendation="BUILD_FROM_SCRATCH",
            )
            self._write_and_transition()

        return self._report or ResearchReport(spec_id=spec_id, decision=ScoutDecision.RESEARCH)

    def _build_sources(self) -> list[Any]:
        """Build the list of search sources based on available tools."""
        sources: list[Any] = [
            GitHubSearchSource(tool_executor=self._tool_executor),
            PyPISearchSource(),
            NpmSearchSource(),
        ]
        return sources

    def _write_and_transition(self) -> None:
        """Write research.md and transition spec to SCOUTED."""
        if not self.context.spec or not self.context.spec.file_path or not self._report:
            return

        spec_dir = str(Path(self.context.spec.file_path).parent)
        write_report(spec_dir, self._report)
        update_spec_status(self.context.spec.file_path, SpecStatus.SCOUTED)
        logger.info("Spec %s transitioned to SCOUTED", self.context.spec.frontmatter.id)


def _extract_content(response: Any) -> str:
    """Extract text content from an LLM response object."""
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


def _parse_queries(content: str) -> list[str]:
    """Parse search queries from LLM response (lines starting with '- ')."""
    queries = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- SUMMARY:"):
            query = stripped[2:].strip()
            if query and not query.startswith("SUMMARY:"):
                queries.append(query)
    return queries


def _parse_summary(content: str) -> str:
    """Parse the SUMMARY line from LLM response."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("SUMMARY:"):
            return stripped[8:].strip()
    return ""


def _recommend(results: list[SearchResult]) -> str:
    """Generate a recommendation based on search results."""
    if not results:
        return "BUILD_FROM_SCRATCH"

    high_relevance = [r for r in results if r.relevance == "HIGH"]
    if len(high_relevance) >= 2:
        return "COMBINE"
    if high_relevance:
        return "USE_LIBRARY"
    if len(results) >= 3:
        return "USE_LIBRARY"
    return "BUILD_FROM_SCRATCH"
