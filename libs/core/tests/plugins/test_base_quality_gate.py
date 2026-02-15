"""Tests for BaseQualityGate ABC."""


class TestBaseQualityGate:
    def test_automated_checks(self, stub_quality_gate) -> None:
        checks = stub_quality_gate.automated_checks
        assert len(checks) == 2
        assert checks[0]["name"] == "tests"
        assert checks[1]["name"] == "lint"

    def test_get_prompt(self, stub_quality_gate, sample_spec) -> None:
        prompt = stub_quality_gate.get_prompt(sample_spec, "diff content", {})
        assert "001-test-feature" in prompt
        assert "diff content" in prompt
