"""Tests for Quality Gate prompt assembly."""

from __future__ import annotations

from vizier.core.agents.quality_gate.prompts import QUALITY_GATE_CORE_PROMPT, QualityGatePromptAssembler


class TestQualityGateCorePrompt:
    def test_contains_role(self) -> None:
        assert "Quality Gate agent" in QUALITY_GATE_CORE_PROMPT

    def test_mentions_quality_verdict(self) -> None:
        assert "QUALITY_VERDICT" in QUALITY_GATE_CORE_PROMPT

    def test_mentions_evidence(self) -> None:
        assert "evidence" in QUALITY_GATE_CORE_PROMPT.lower()

    def test_mentions_run_tests_mandatory(self) -> None:
        assert "run_tests" in QUALITY_GATE_CORE_PROMPT
        assert "MANDATORY" in QUALITY_GATE_CORE_PROMPT or "MUST" in QUALITY_GATE_CORE_PROMPT

    def test_mentions_multi_pass(self) -> None:
        assert "Pass 1" in QUALITY_GATE_CORE_PROMPT
        assert "Pass 2" in QUALITY_GATE_CORE_PROMPT
        assert "Pass 3" in QUALITY_GATE_CORE_PROMPT
        assert "Pass 4" in QUALITY_GATE_CORE_PROMPT

    def test_pass_1_is_hygiene(self) -> None:
        assert "Hygiene" in QUALITY_GATE_CORE_PROMPT

    def test_pass_2_is_mechanical(self) -> None:
        assert "Mechanical" in QUALITY_GATE_CORE_PROMPT

    def test_mentions_done_and_rejected(self) -> None:
        assert "DONE" in QUALITY_GATE_CORE_PROMPT
        assert "REJECTED" in QUALITY_GATE_CORE_PROMPT

    def test_lists_all_tools(self) -> None:
        for tool in [
            "read_file",
            "glob",
            "grep",
            "bash",
            "run_tests",
            "update_spec_status",
            "write_feedback",
            "send_message",
            "ping_supervisor",
        ]:
            assert tool in QUALITY_GATE_CORE_PROMPT

    def test_mentions_evidence_files(self) -> None:
        assert "test_output.txt" in QUALITY_GATE_CORE_PROMPT
        assert "lint_output.txt" in QUALITY_GATE_CORE_PROMPT


class TestQualityGatePromptAssembler:
    def test_core_only(self) -> None:
        assembler = QualityGatePromptAssembler()
        prompt = assembler.assemble()
        assert "Quality Gate agent" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = QualityGatePromptAssembler()
        assert assembler.core_prompt == QUALITY_GATE_CORE_PROMPT

    def test_with_acceptance_criteria(self) -> None:
        assembler = QualityGatePromptAssembler(acceptance_criteria="1. All tests pass\n2. Type check clean")
        prompt = assembler.assemble()
        assert "Acceptance Criteria for This Spec" in prompt
        assert "All tests pass" in prompt

    def test_without_acceptance_criteria(self) -> None:
        assembler = QualityGatePromptAssembler()
        prompt = assembler.assemble()
        assert "Acceptance Criteria for This Spec" not in prompt

    def test_with_quality_guide(self) -> None:
        assembler = QualityGatePromptAssembler(quality_guide="Run integration tests with docker-compose")
        prompt = assembler.assemble()
        assert "Plugin Quality Guide" in prompt
        assert "docker-compose" in prompt

    def test_without_quality_guide(self) -> None:
        assembler = QualityGatePromptAssembler()
        prompt = assembler.assemble()
        assert "Plugin Quality Guide" not in prompt

    def test_both_modules(self) -> None:
        assembler = QualityGatePromptAssembler(
            acceptance_criteria="JWT tokens validated correctly",
            quality_guide="Check code coverage exceeds threshold",
        )
        prompt = assembler.assemble()
        assert "JWT tokens validated correctly" in prompt
        assert "coverage exceeds threshold" in prompt

    def test_ordering(self) -> None:
        assembler = QualityGatePromptAssembler(
            acceptance_criteria="JWT tokens validated correctly",
            quality_guide="Coverage exceeds threshold",
        )
        prompt = assembler.assemble()
        assert prompt.index("Quality Gate agent") < prompt.index("JWT tokens validated")
        assert prompt.index("JWT tokens validated") < prompt.index("Coverage exceeds threshold")
