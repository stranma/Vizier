"""Tests for Retrospective prompt assembly."""

from __future__ import annotations

from vizier.core.agents.retrospective.prompts import RETROSPECTIVE_CORE_PROMPT, RetrospectivePromptAssembler


class TestRetrospectiveCorePrompt:
    def test_contains_role(self) -> None:
        assert "Retrospective agent" in RETROSPECTIVE_CORE_PROMPT

    def test_mentions_golden_trace(self) -> None:
        assert "trace" in RETROSPECTIVE_CORE_PROMPT.lower()

    def test_mentions_process_debt(self) -> None:
        assert "process debt" in RETROSPECTIVE_CORE_PROMPT.lower()

    def test_mentions_evidence_based(self) -> None:
        assert "evidence" in RETROSPECTIVE_CORE_PROMPT.lower()

    def test_mentions_sultan_approval(self) -> None:
        assert "Sultan approval" in RETROSPECTIVE_CORE_PROMPT

    def test_mentions_learnings(self) -> None:
        assert "learnings.md" in RETROSPECTIVE_CORE_PROMPT

    def test_mentions_metrics(self) -> None:
        assert "rejection rate" in RETROSPECTIVE_CORE_PROMPT.lower()
        assert "stuck rate" in RETROSPECTIVE_CORE_PROMPT.lower()

    def test_lists_all_tools(self) -> None:
        for tool in ["read_file", "glob", "grep", "read_spec", "list_specs", "send_message"]:
            assert tool in RETROSPECTIVE_CORE_PROMPT

    def test_mentions_proposals_dir(self) -> None:
        assert "proposals" in RETROSPECTIVE_CORE_PROMPT


class TestRetrospectivePromptAssembler:
    def test_core_only(self) -> None:
        assembler = RetrospectivePromptAssembler()
        prompt = assembler.assemble()
        assert "Retrospective agent" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = RetrospectivePromptAssembler()
        assert assembler.core_prompt == RETROSPECTIVE_CORE_PROMPT

    def test_with_metrics(self) -> None:
        assembler = RetrospectivePromptAssembler(metrics_summary="Rejection rate: 15%")
        prompt = assembler.assemble()
        assert "Current Metrics" in prompt
        assert "15%" in prompt

    def test_without_metrics(self) -> None:
        assembler = RetrospectivePromptAssembler()
        prompt = assembler.assemble()
        assert "Current Metrics" not in prompt

    def test_with_debt_register(self) -> None:
        assembler = RetrospectivePromptAssembler(debt_register="- [OPEN] Repeated lint failures")
        prompt = assembler.assemble()
        assert "Known Process Debt" in prompt
        assert "lint failures" in prompt

    def test_without_debt_register(self) -> None:
        assembler = RetrospectivePromptAssembler()
        prompt = assembler.assemble()
        assert "Known Process Debt" not in prompt

    def test_both_modules(self) -> None:
        assembler = RetrospectivePromptAssembler(
            metrics_summary="Stuck rate: 5%",
            debt_register="- [HIGH] Budget overruns",
        )
        prompt = assembler.assemble()
        assert "5%" in prompt
        assert "Budget overruns" in prompt
