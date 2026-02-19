"""Tests for DocumentsPlugin."""

from __future__ import annotations

from vizier.plugins.documents.plugin import DocumentsPlugin


class TestDocumentsPlugin:
    def test_name(self) -> None:
        plugin = DocumentsPlugin()
        assert plugin.name == "documents"

    def test_description(self) -> None:
        plugin = DocumentsPlugin()
        assert "document" in plugin.description.lower()

    def test_worker_write_set_patterns(self) -> None:
        plugin = DocumentsPlugin()
        patterns = plugin.worker_write_set
        assert "docs/**" in patterns
        assert "templates/**" in patterns
        assert "assets/**" in patterns

    def test_required_evidence(self) -> None:
        plugin = DocumentsPlugin()
        evidence = plugin.required_evidence
        assert "link_check_output" in evidence
        assert "structure_validation" in evidence
        assert "rendered_preview_path" in evidence

    def test_system_prompts_has_all_roles(self) -> None:
        plugin = DocumentsPlugin()
        prompts = plugin.system_prompts
        assert "scout" in prompts
        assert "architect" in prompts
        assert "worker" in prompts
        assert "quality_gate" in prompts

    def test_scout_guide(self) -> None:
        plugin = DocumentsPlugin()
        guide = plugin.get_scout_guide()
        assert "template" in guide.lower()

    def test_architect_guide(self) -> None:
        plugin = DocumentsPlugin()
        guide = plugin.get_architect_guide()
        assert "section" in guide.lower()

    def test_worker_guide(self) -> None:
        plugin = DocumentsPlugin()
        guide = plugin.get_worker_guide()
        assert "formatting" in guide.lower()

    def test_quality_gate_guide(self) -> None:
        plugin = DocumentsPlugin()
        guide = plugin.get_quality_gate_guide()
        assert "link" in guide.lower()

    def test_tool_overrides_bash(self) -> None:
        plugin = DocumentsPlugin()
        overrides = plugin.tool_overrides
        assert "bash" in overrides

    def test_default_model_tiers(self) -> None:
        plugin = DocumentsPlugin()
        tiers = plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["architect"] == "opus"
