"""Software development plugin: SoftwarePlugin, SoftwareCoder, SoftwareQualityGate."""

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
You are a software development agent. Your job is to implement the task \
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

1. Read the relevant source files to understand the current codebase
2. Plan your changes before writing code
3. Write clean, well-typed code following project conventions
4. Write or update tests for your changes
5. Verify your changes work by running tests
6. Do NOT leave debug prints, TODO markers, or commented-out code
7. When complete, exit cleanly (do not output any completion signal)
"""

QUALITY_GATE_PROMPT = """\
You are a software quality gate agent. Your job is to validate the \
implementation against the spec's acceptance criteria.

## Spec Under Review

- **ID:** {spec_id}
- **Complexity:** {complexity}

## Task Description

{content}

## Changes Made (Diff)

{diff}

## Evaluation

Review the diff against the spec requirements. Check:

1. **Correctness**: Does the implementation satisfy all requirements?
2. **Test coverage**: Are new/changed functions tested?
3. **Code quality**: Clean code, no debug artifacts, proper types?
4. **Edge cases**: Are boundary conditions handled?

Respond with a structured verdict:
- PASS: All criteria met, implementation is correct
- FAIL: Issues found (list each with specific feedback)
"""

ARCHITECT_GUIDE = """\
## Software Task Decomposition Guide

When decomposing a software task, follow these patterns:

### Feature Implementation
1. **Data models** -- Define types, schemas, and data structures first
2. **Core logic** -- Implement business logic with clear interfaces
3. **Integration** -- Wire into existing systems, add API endpoints
4. **Tests** -- Write unit and integration tests

### Bug Fix
1. **Reproduce** -- Write a failing test that demonstrates the bug
2. **Fix** -- Make the minimal change to fix the issue
3. **Verify** -- Confirm the test passes and no regressions

### Refactoring
1. **Tests first** -- Ensure comprehensive test coverage before refactoring
2. **Extract** -- Move code to new locations/abstractions
3. **Verify** -- All existing tests still pass

### Complexity Guidelines
- **Low**: Single file change, simple logic, clear requirements
- **Medium**: 2-5 files, moderate logic, some design decisions
- **High**: 5+ files, complex logic, architectural decisions needed

### Sub-Spec Format
Each sub-spec should specify:
- A clear, actionable title
- The files to create or modify
- Acceptance criteria referencing @criteria/ entries
- Complexity estimate (low/medium/high)
"""


class SoftwareCoder(BaseWorker):
    """Worker agent for software development tasks.

    Uses file operations, bash commands, and git to implement specs.
    """

    @property
    def allowed_tools(self) -> list[str]:
        return ["file_read", "file_write", "bash", "git"]

    @property
    def tool_restrictions(self) -> dict[str, dict[str, list[str]]]:
        return {
            "bash": {
                "denied_patterns": [
                    r"rm\s+-rf\b",
                    r"sudo\s+",
                    r"curl.*\|\s*(?:ba)?sh",
                    r"wget.*\|\s*(?:ba)?sh",
                ],
            },
            "git": {
                "denied_patterns": [
                    r"push\s+--force",
                    r"reset\s+--hard\s+origin",
                ],
            },
        }

    @property
    def git_strategy(self) -> str:
        return "branch_per_spec"

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


class SoftwareQualityGate(BaseQualityGate):
    """Quality gate for software development: runs pytest, ruff, and validates test quality."""

    @property
    def automated_checks(self) -> list[dict[str, str]]:
        return [
            {"name": "tests_pass", "command": "uv run pytest -q"},
            {"name": "lint_clean", "command": "uv run ruff check ."},
            {"name": "type_check", "command": "uv run pyright"},
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


class SoftwarePlugin(BasePlugin):
    """Built-in software development plugin.

    Provides SoftwareCoder worker with file/bash/git tools,
    SoftwareQualityGate with pytest/ruff/pyright checks,
    and decomposition guidance for feature/bugfix/refactor patterns.
    """

    @property
    def name(self) -> str:
        return "software"

    @property
    def description(self) -> str:
        return "Software development plugin with coding, testing, and quality validation"

    @property
    def worker_class(self) -> type[BaseWorker]:
        return SoftwareCoder

    @property
    def quality_gate_class(self) -> type[BaseQualityGate]:
        return SoftwareQualityGate

    @property
    def default_model_tiers(self) -> dict[str, str]:
        return {
            "worker": "sonnet",
            "quality_gate": "sonnet",
            "architect": "opus",
        }

    def get_architect_guide(self) -> str:
        """Return software-specific decomposition guidance."""
        return ARCHITECT_GUIDE

    def get_criteria_library(self) -> dict[str, str]:
        """Return the software criteria library loaded from criteria/ markdown files."""
        loader = CriteriaLibraryLoader(_CRITERIA_DIR)
        return loader.load()
