"""Tests for the stub plugin fixture."""

from __future__ import annotations

import pytest

from vizier.core.models.spec import Spec, SpecComplexity, SpecFrontmatter, SpecStatus
from vizier.core.plugins.discovery import clear_registry, register_plugin

from . import StubPlugin, StubQualityGate, StubWorker


@pytest.fixture()
def stub_plugin() -> StubPlugin:
    return StubPlugin()


@pytest.fixture()
def sample_spec() -> Spec:
    return Spec(
        frontmatter=SpecFrontmatter(
            id="001-test-task",
            status=SpecStatus.READY,
            priority=1,
            complexity=SpecComplexity.LOW,
            plugin="test-stub",
        ),
        content="Create a file called output.txt with the text 'hello world'.",
    )


class TestStubPlugin:
    def test_name(self, stub_plugin: StubPlugin) -> None:
        assert stub_plugin.name == "test-stub"

    def test_description(self, stub_plugin: StubPlugin) -> None:
        assert stub_plugin.description != ""

    def test_worker_class(self, stub_plugin: StubPlugin) -> None:
        assert stub_plugin.worker_class is StubWorker

    def test_quality_gate_class(self, stub_plugin: StubPlugin) -> None:
        assert stub_plugin.quality_gate_class is StubQualityGate

    def test_default_model_tiers(self, stub_plugin: StubPlugin) -> None:
        tiers = stub_plugin.default_model_tiers
        assert tiers["worker"] == "haiku"
        assert tiers["quality_gate"] == "haiku"
        assert tiers["architect"] == "opus"

    def test_architect_guide(self, stub_plugin: StubPlugin) -> None:
        guide = stub_plugin.get_architect_guide()
        assert "decompose" in guide.lower() or "file" in guide.lower()

    def test_criteria_library(self, stub_plugin: StubPlugin) -> None:
        library = stub_plugin.get_criteria_library()
        assert "file_exists" in library
        assert "non-empty" in library["file_exists"].lower()

    def test_programmatic_registration(self, stub_plugin: StubPlugin) -> None:
        register_plugin("test-stub", StubPlugin)
        from vizier.core.plugins.discovery import discover_plugins

        plugins = discover_plugins()
        assert "test-stub" in plugins
        assert plugins["test-stub"].name == "test-stub"
        clear_registry()


class TestStubWorker:
    def test_allowed_tools(self) -> None:
        worker = StubWorker()
        assert "file_read" in worker.allowed_tools
        assert "file_write" in worker.allowed_tools

    def test_no_tool_restrictions(self) -> None:
        worker = StubWorker()
        assert worker.tool_restrictions == {}

    def test_git_strategy(self) -> None:
        worker = StubWorker()
        assert worker.git_strategy == "commit_to_main"

    def test_get_prompt(self, sample_spec: Spec) -> None:
        worker = StubWorker()
        prompt = worker.get_prompt(sample_spec, {"constitution": "Be helpful"})
        assert "001-test-task" in prompt
        assert "output.txt" in prompt
        assert "Be helpful" in prompt


class TestStubQualityGate:
    def test_automated_checks(self) -> None:
        gate = StubQualityGate()
        checks = gate.automated_checks
        assert len(checks) >= 1
        assert checks[0]["name"] == "file_exists"

    def test_get_prompt(self, sample_spec: Spec) -> None:
        gate = StubQualityGate()
        prompt = gate.get_prompt(sample_spec, "diff content here", {})
        assert "001-test-task" in prompt
        assert "diff content here" in prompt
