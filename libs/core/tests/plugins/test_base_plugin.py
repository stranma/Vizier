"""Tests for BasePlugin ABC."""

from tests.plugins.conftest import StubQualityGate, StubWorker


class TestBasePlugin:
    def test_name(self, stub_plugin) -> None:
        assert stub_plugin.name == "stub"

    def test_description(self, stub_plugin) -> None:
        assert stub_plugin.description == "Stub plugin for testing"

    def test_worker_class(self, stub_plugin) -> None:
        assert stub_plugin.worker_class is StubWorker

    def test_quality_gate_class(self, stub_plugin) -> None:
        assert stub_plugin.quality_gate_class is StubQualityGate

    def test_default_model_tiers(self, stub_plugin) -> None:
        tiers = stub_plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["quality_gate"] == "sonnet"
        assert tiers["architect"] == "opus"

    def test_architect_guide_default_empty(self, stub_plugin) -> None:
        assert stub_plugin.get_architect_guide() == ""

    def test_criteria_library(self, stub_plugin) -> None:
        lib = stub_plugin.get_criteria_library()
        assert "tests_pass" in lib
        assert "lint_clean" in lib
