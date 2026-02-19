"""Tests for SoftwarePlugin."""

from __future__ import annotations

from vizier.plugins.software.plugin import SoftwarePlugin


class TestSoftwarePlugin:
    def test_name(self) -> None:
        plugin = SoftwarePlugin()
        assert plugin.name == "software"

    def test_description(self) -> None:
        plugin = SoftwarePlugin()
        assert "software" in plugin.description.lower()

    def test_worker_write_set_patterns(self) -> None:
        plugin = SoftwarePlugin()
        patterns = plugin.worker_write_set
        assert "src/**/*.py" in patterns
        assert "tests/**/*.py" in patterns
        assert "docs/**/*.md" in patterns
        assert "pyproject.toml" in patterns

    def test_required_evidence(self) -> None:
        plugin = SoftwarePlugin()
        evidence = plugin.required_evidence
        assert "test_output" in evidence
        assert "lint_output" in evidence
        assert "type_check_output" in evidence
        assert "diff" in evidence

    def test_system_prompts_has_all_roles(self) -> None:
        plugin = SoftwarePlugin()
        prompts = plugin.system_prompts
        assert "scout" in prompts
        assert "architect" in prompts
        assert "worker" in prompts
        assert "quality_gate" in prompts

    def test_scout_guide(self) -> None:
        plugin = SoftwarePlugin()
        guide = plugin.get_scout_guide()
        assert "PyPI" in guide
        assert "GitHub" in guide

    def test_architect_guide(self) -> None:
        plugin = SoftwarePlugin()
        guide = plugin.get_architect_guide()
        assert "layered" in guide.lower()
        assert "Data models" in guide

    def test_worker_guide(self) -> None:
        plugin = SoftwarePlugin()
        guide = plugin.get_worker_guide()
        assert "TDD" in guide
        assert "type annotation" in guide.lower()

    def test_quality_gate_guide(self) -> None:
        plugin = SoftwarePlugin()
        guide = plugin.get_quality_gate_guide()
        assert "pytest" in guide
        assert "ruff" in guide

    def test_tool_overrides_bash(self) -> None:
        plugin = SoftwarePlugin()
        overrides = plugin.tool_overrides
        assert "bash" in overrides
        assert "denied_patterns" in overrides["bash"]

    def test_default_model_tiers(self) -> None:
        plugin = SoftwarePlugin()
        tiers = plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["architect"] == "opus"
