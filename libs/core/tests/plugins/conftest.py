"""Test fixtures: stub plugin, worker, and quality gate implementations."""

from __future__ import annotations

import pytest

from vizier.core.models.spec import Spec, SpecFrontmatter
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker


class StubWorker(BaseWorker):
    @property
    def allowed_tools(self) -> list[str]:
        return ["file_read", "file_write", "file_edit", "bash", "git", "glob", "grep"]

    @property
    def tool_restrictions(self) -> dict[str, dict[str, list[str]]]:
        return {
            "bash": {
                "allowed_patterns": [r"uv run pytest.*", r"uv run ruff.*", r"npm test.*"],
                "denied_patterns": [r"rm -rf.*", r"curl.*", r"wget.*"],
            }
        }

    def get_prompt(self, spec: Spec, context: dict) -> str:
        return f"Implement {spec.frontmatter.id}: {spec.content}"


class StubQualityGate(BaseQualityGate):
    @property
    def automated_checks(self) -> list[dict[str, str]]:
        return [
            {"name": "tests", "command": "uv run pytest {spec_test_files} -v"},
            {"name": "lint", "command": "uv run ruff check {spec_files}"},
        ]

    def get_prompt(self, spec: Spec, diff: str, context: dict) -> str:
        return f"Validate {spec.frontmatter.id} with diff:\n{diff}"


class StubPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "stub"

    @property
    def description(self) -> str:
        return "Stub plugin for testing"

    @property
    def worker_class(self) -> type[BaseWorker]:
        return StubWorker

    @property
    def quality_gate_class(self) -> type[BaseQualityGate]:
        return StubQualityGate

    def get_criteria_library(self) -> dict[str, str]:
        return {
            "tests_pass": "All tests must pass.",
            "lint_clean": "Code must pass linting.",
        }


@pytest.fixture
def stub_plugin() -> StubPlugin:
    return StubPlugin()


@pytest.fixture
def stub_worker() -> StubWorker:
    return StubWorker()


@pytest.fixture
def stub_quality_gate() -> StubQualityGate:
    return StubQualityGate()


@pytest.fixture
def sample_spec() -> Spec:
    fm = SpecFrontmatter(id="001-test-feature", plugin="stub")
    return Spec(frontmatter=fm, content="# Test Feature\n\n## Requirements\n\n- MUST do X")
