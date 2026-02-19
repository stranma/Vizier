"""Tests for BasePlugin ABC."""


class TestBasePlugin:
    def test_name(self, stub_plugin) -> None:
        assert stub_plugin.name == "stub"

    def test_description(self, stub_plugin) -> None:
        assert stub_plugin.description == "Stub plugin for testing"

    def test_default_model_tiers(self, stub_plugin) -> None:
        tiers = stub_plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["quality_gate"] == "sonnet"
        assert tiers["architect"] == "opus"

    def test_architect_guide_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.get_architect_guide() == ""

    def test_scout_guide_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.get_scout_guide() == ""

    def test_worker_guide_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.get_worker_guide() == ""

    def test_quality_gate_guide_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.get_quality_gate_guide() == ""

    def test_criteria_library(self, stub_plugin) -> None:
        lib = stub_plugin.get_criteria_library()
        assert "tests_pass" in lib
        assert "lint_clean" in lib

    def test_worker_write_set_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.worker_write_set == []

    def test_required_evidence_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.required_evidence == []

    def test_system_prompts_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.system_prompts == {}

    def test_tool_overrides_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.tool_overrides == {}
