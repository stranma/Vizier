"""Architect agent runtime: decomposes DRAFT specs into READY sub-specs."""

from __future__ import annotations

import logging
from typing import Any

from vizier.core.agent.base import BaseAgent
from vizier.core.architect.decomposition import (
    SubSpecDefinition,
    generate_sub_spec_id,
    parse_decomposition,
)
from vizier.core.file_protocol.spec_io import create_spec, update_spec_status
from vizier.core.models.spec import Spec, SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin  # noqa: TC001

logger = logging.getLogger(__name__)


class ArchitectRuntime(BaseAgent):
    """Architect agent that decomposes DRAFT specs into implementable sub-specs.

    Reads the project context, plugin's architect guide, and criteria library.
    Produces sub-specs with acceptance criteria, complexity estimates, and
    artifact lists. Marks the parent spec as DECOMPOSED.

    :param context: Agent context loaded from disk.
    :param plugin: The project's plugin instance.
    :param llm_callable: LLM completion function.
    :param model_router: Optional model router.
    :param logger_instance: Optional agent logger.
    """

    def __init__(
        self,
        context: Any,
        plugin: BasePlugin,
        llm_callable: Any = None,
        model_router: Any = None,
        logger_instance: Any = None,
    ) -> None:
        super().__init__(
            context=context,
            model_router=model_router,
            logger=logger_instance,
            llm_callable=llm_callable,
        )
        self._plugin = plugin
        self._created_specs: list[Spec] = []

    @property
    def role(self) -> str:
        return "architect"

    @property
    def created_specs(self) -> list[Spec]:
        """Sub-specs created during decomposition."""
        return list(self._created_specs)

    def build_prompt(self) -> str:
        """Build the Architect's prompt with spec, project context, and plugin guide.

        :returns: Rendered prompt string.
        :raises RuntimeError: If no spec is loaded in context.
        """
        if not self.context.spec:
            raise RuntimeError("Architect requires a spec to decompose")

        spec = self.context.spec
        guide = self._plugin.get_architect_guide()
        criteria_library = self._plugin.get_criteria_library()

        criteria_section = ""
        if criteria_library:
            criteria_items = "\n".join(f"- @criteria/{name}: {defn}" for name, defn in criteria_library.items())
            criteria_section = f"\n\n## Available Criteria Library\n{criteria_items}"

        return (
            f"# Architect: Decompose Task into Sub-specs\n\n"
            f"You are the Architect agent. Your job is to decompose this task into "
            f"implementable sub-specs that Workers can execute independently.\n\n"
            f"## Task to Decompose\n\n"
            f"**Spec ID:** {spec.frontmatter.id}\n"
            f"**Plugin:** {spec.frontmatter.plugin}\n"
            f"**Complexity:** {spec.frontmatter.complexity}\n\n"
            f"### Description\n{spec.content}\n\n"
            f"## Project Context\n\n"
            f"### Constitution\n{self.context.constitution or 'No constitution defined.'}\n\n"
            f"### Learnings\n{self.context.learnings or 'No learnings recorded yet.'}\n\n"
            f"## Plugin Decomposition Guide\n{guide or 'No specific decomposition guide.'}\n"
            f"{criteria_section}\n\n"
            f"## Output Format\n\n"
            f"For each sub-spec, use this exact format:\n\n"
            f"## Sub-spec: <title>\n"
            f"Complexity: low|medium|high\n"
            f"Priority: <number>\n"
            f"Artifacts: <comma-separated file paths>\n\n"
            f"<detailed description with acceptance criteria>\n"
            f"Reference criteria from the library using @criteria/<name> syntax.\n\n"
            f"## Rules\n"
            f"- One concern per sub-spec\n"
            f"- Include specific acceptance criteria for each sub-spec\n"
            f"- Set complexity honestly (drives Worker model selection)\n"
            f"- Reference learnings.md for known pitfalls\n"
            f"- Sub-specs must be independently implementable\n"
        )

    def process_response(self, response: Any) -> str:
        """Parse LLM response into sub-specs and create them on disk.

        :param response: LLM completion response.
        :returns: "DECOMPOSED" on success.
        """
        content = _extract_content(response)
        sub_spec_defs = parse_decomposition(content)

        if not sub_spec_defs:
            logger.warning("Architect produced no sub-specs from response")
            return "DECOMPOSED"

        self._create_sub_specs(sub_spec_defs)
        self._mark_parent_decomposed()

        return "DECOMPOSED"

    def decompose(self) -> list[Spec]:
        """Run the full decomposition flow: prompt -> LLM -> create sub-specs.

        :returns: List of created sub-spec Spec objects.
        :raises RuntimeError: If no LLM callable or no spec.
        """
        self.run()
        return self._created_specs

    def _create_sub_specs(self, definitions: list[SubSpecDefinition]) -> None:
        """Create sub-spec files on disk from parsed definitions.

        :param definitions: Parsed sub-spec definitions.
        """
        if not self.context.spec:
            return

        parent_id = self.context.spec.frontmatter.id
        parent_plugin = self.context.spec.frontmatter.plugin

        for i, defn in enumerate(definitions, start=1):
            sub_id = generate_sub_spec_id(parent_id, i, defn.title)

            spec = create_spec(
                self.context.project_root,
                sub_id,
                defn.description,
                {
                    "status": "READY",
                    "priority": defn.priority,
                    "complexity": defn.complexity,
                    "parent": parent_id,
                    "plugin": parent_plugin,
                },
            )
            self._created_specs.append(spec)
            logger.info("Created sub-spec %s (complexity=%s, priority=%d)", sub_id, defn.complexity, defn.priority)

    def _mark_parent_decomposed(self) -> None:
        """Transition the parent spec to DECOMPOSED status."""
        if not self.context.spec or not self.context.spec.file_path:
            return

        update_spec_status(self.context.spec.file_path, SpecStatus.DECOMPOSED)
        logger.info("Marked parent spec %s as DECOMPOSED", self.context.spec.frontmatter.id)


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
