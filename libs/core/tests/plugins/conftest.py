"""Test fixtures for plugin tests."""

from __future__ import annotations

import pytest

from vizier.core.models.spec import Spec, SpecFrontmatter
from vizier.core.plugins.base_plugin import BasePlugin


class StubPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "stub"

    @property
    def description(self) -> str:
        return "Stub plugin for testing"

    def get_criteria_library(self) -> dict[str, str]:
        return {
            "tests_pass": "All tests must pass.",
            "lint_clean": "Code must pass linting.",
        }


@pytest.fixture
def stub_plugin() -> StubPlugin:
    return StubPlugin()


@pytest.fixture
def sample_spec() -> Spec:
    fm = SpecFrontmatter(id="001-test-feature", plugin="stub")
    return Spec(frontmatter=fm, content="# Test Feature\n\n## Requirements\n\n- MUST do X")
