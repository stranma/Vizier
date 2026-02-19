"""Software development plugin for Vizier.

Defines write-set patterns, required evidence types, system prompt guides,
and criteria library for software development projects.
"""

from __future__ import annotations

from vizier.core.plugins.base_plugin import BasePlugin


class SoftwarePlugin(BasePlugin):
    """Plugin for software development projects.

    Provides write-set patterns for source and test files, requires
    test/lint/type-check/diff evidence, and includes role-specific
    system prompt guides for Scout, Architect, Worker, and Quality Gate.
    """

    @property
    def name(self) -> str:
        return "software"

    @property
    def description(self) -> str:
        return "Software development plugin: code, tests, CI"

    @property
    def worker_write_set(self) -> list[str]:
        return [
            "src/**/*.py",
            "tests/**/*.py",
            "docs/**/*.md",
            "pyproject.toml",
            "*.cfg",
            "*.toml",
            "*.ini",
        ]

    @property
    def required_evidence(self) -> list[str]:
        return [
            "test_output",
            "lint_output",
            "type_check_output",
            "diff",
        ]

    @property
    def system_prompts(self) -> dict[str, str]:
        return {
            "scout": SCOUT_GUIDE,
            "architect": ARCHITECT_GUIDE,
            "worker": WORKER_GUIDE,
            "quality_gate": QUALITY_GATE_GUIDE,
        }

    @property
    def tool_overrides(self) -> dict[str, dict[str, list[str]]]:
        return {
            "bash": {
                "denied_patterns": [
                    r"rm\s+-rf\s+/",
                    r"mkfs",
                    r"dd\s+if=",
                ],
            },
        }


SCOUT_GUIDE = """\
Research existing Python packages on PyPI and GitHub repositories.
Check for:
- Existing libraries that solve the task (or parts of it)
- Common patterns and best practices for the domain
- Known issues or gotchas with related packages
- License compatibility (prefer MIT, Apache-2.0, BSD)

Search sources: PyPI JSON API, GitHub search (via gh CLI), npm (if JS interop needed).
"""

ARCHITECT_GUIDE = """\
Decompose using the layered pattern:
1. Data models and schemas first (no dependencies)
2. Business logic / service layer (depends on models)
3. API endpoints / CLI commands (depends on logic)
4. Integration tests (depends on all above)

Each sub-spec should:
- Target one module or closely related set of files
- Include specific acceptance criteria referencing @criteria/ library
- Declare write-set patterns scoped to its concern
- Set complexity based on: LOW (config, rename), MEDIUM (new feature), HIGH (architectural change)
"""

WORKER_GUIDE = """\
Follow TDD workflow:
1. Write failing tests first (when appropriate)
2. Implement the minimum code to pass tests
3. Refactor for clarity

Quality expectations:
- Type annotations on all public functions
- Docstrings on public APIs (reStructuredText format)
- No print statements or debug artifacts
- Run ruff check + pyright before committing
"""

QUALITY_GATE_GUIDE = """\
Mechanical checks (MUST pass before LLM review):
1. pytest: all tests must pass
2. ruff check: no lint errors
3. pyright: no type errors
4. git diff: only files in write-set modified

Semantic checks (LLM-assisted):
- Tests are meaningful (not just assert True)
- Edge cases covered (empty input, error paths)
- No security vulnerabilities (injection, hardcoded secrets)
- Code follows project conventions (check pyproject.toml for settings)
"""
