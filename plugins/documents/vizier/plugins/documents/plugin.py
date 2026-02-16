"""Document production plugin: DocumentsPlugin, DocumentWriter, DocumentReviewer."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.criteria_loader import CriteriaLibraryLoader

if TYPE_CHECKING:
    from vizier.core.models.spec import Spec

_CRITERIA_DIR = Path(__file__).parent / "criteria"


WORKER_PROMPT = """\
You are a document production agent. Your job is to produce the document \
described in the spec below.

## Spec

- **ID:** {spec_id}
- **Priority:** {priority}
- **Complexity:** {complexity}

## Task

{content}

## Project Context

{constitution}

## Learnings from Previous Work

{learnings}

## Instructions

1. Read the source materials and references cited in the task
2. Plan the document structure before writing
3. Write clear, well-organized content with proper headings and sections
4. Cite sources for key facts and claims
5. Ensure consistent formatting throughout the document
6. Do NOT leave placeholder text, TODO markers, or incomplete sections
7. When complete, exit cleanly (do not output any completion signal)
"""

QUALITY_GATE_PROMPT = """\
You are a document quality gate agent. Your job is to validate the \
document against the spec's acceptance criteria.

## Spec Under Review

- **ID:** {spec_id}
- **Complexity:** {complexity}

## Task Description

{content}

## Changes Made (Diff)

{diff}

## Evaluation

Review the diff against the spec requirements. Check:

1. **Structure**: Are all required sections present in logical order?
2. **Content completeness**: Does the document cover all requested topics?
3. **Factual accuracy**: Are claims supported with citations or sources?
4. **Formatting**: Consistent headings, lists, tables, and styling?

Respond with a structured verdict:
- PASS: All criteria met, document is complete and well-formed
- FAIL: Issues found (list each with specific feedback)
"""

ARCHITECT_GUIDE = """\
## Document Task Decomposition Guide

When decomposing a document production task, follow these patterns:

### Report
1. **Research** -- Gather source materials and data
2. **Outline** -- Create section structure and key points
3. **Draft** -- Write content for each section
4. **Review** -- Verify accuracy, citations, and formatting

### Proposal
1. **Context** -- Define the problem and audience
2. **Solution** -- Draft the proposed approach and benefits
3. **Evidence** -- Add supporting data and references
4. **Polish** -- Executive summary, formatting, and review

### Memo
1. **Purpose** -- Define the key message and audience
2. **Body** -- Write the main content concisely
3. **Action items** -- List next steps or decisions needed

### Complexity Guidelines
- **Low**: Single-section document, straightforward content, clear requirements
- **Medium**: Multi-section document, requires research, some formatting decisions
- **High**: Long-form document, multiple sources, complex layout and review

### Sub-Spec Format
Each sub-spec should specify:
- A clear, actionable title
- The sections to produce or modify
- Acceptance criteria referencing @criteria/ entries
- Complexity estimate (low/medium/high)
"""


class DocumentWriter(BaseWorker):
    """Worker agent for document production tasks.

    Uses file operations and web search to produce documents.
    """

    @property
    def allowed_tools(self) -> list[str]:
        return ["file_read", "file_write", "web_search"]

    @property
    def tool_restrictions(self) -> dict[str, dict[str, list[str]]]:
        return {}

    @property
    def git_strategy(self) -> str:
        return "commit_to_main"

    def get_prompt(self, spec: Spec, context: dict[str, str]) -> str:
        """Render the worker prompt for a given spec.

        :param spec: The spec to implement.
        :param context: Project context dict.
        :returns: Rendered prompt string.
        """
        return WORKER_PROMPT.format(
            spec_id=spec.frontmatter.id,
            priority=spec.frontmatter.priority,
            complexity=spec.frontmatter.complexity,
            content=spec.content,
            constitution=context.get("constitution", "No project constitution available."),
            learnings=context.get("learnings", "No learnings available."),
        )


class DocumentReviewer(BaseQualityGate):
    """Quality gate for document production: checks output existence, completeness, and formatting."""

    @property
    def automated_checks(self) -> list[dict[str, str]]:
        return [
            {"name": "output_exists", "command": "ls output/"},
            {"name": "no_placeholders", "command": "grep -rL TODO output/"},
        ]

    def get_prompt(self, spec: Spec, diff: str, context: dict[str, str]) -> str:
        """Render the quality gate prompt for validation.

        :param spec: The spec being validated.
        :param diff: Git diff of the worker's changes.
        :param context: Project context dict.
        :returns: Rendered prompt string.
        """
        return QUALITY_GATE_PROMPT.format(
            spec_id=spec.frontmatter.id,
            complexity=spec.frontmatter.complexity,
            content=spec.content,
            diff=diff or "No diff available.",
        )


class DocumentsPlugin(BasePlugin):
    """Built-in document production plugin.

    Provides DocumentWriter with file/web tools,
    DocumentReviewer with output validation checks,
    and decomposition guidance for report/proposal/memo patterns.
    """

    @property
    def name(self) -> str:
        return "documents"

    @property
    def description(self) -> str:
        return "Document production plugin with writing, formatting, and quality review"

    @property
    def worker_class(self) -> type[BaseWorker]:
        return DocumentWriter

    @property
    def quality_gate_class(self) -> type[BaseQualityGate]:
        return DocumentReviewer

    @property
    def default_model_tiers(self) -> dict[str, str]:
        return {
            "worker": "sonnet",
            "quality_gate": "sonnet",
            "architect": "opus",
        }

    def get_architect_guide(self) -> str:
        """Return document-specific decomposition guidance."""
        return ARCHITECT_GUIDE

    def get_criteria_library(self) -> dict[str, str]:
        """Return the document criteria library loaded from criteria/ markdown files."""
        loader = CriteriaLibraryLoader(_CRITERIA_DIR)
        return loader.load()
