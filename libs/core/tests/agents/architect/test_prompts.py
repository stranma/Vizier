"""Tests for Architect prompt assembly."""

from __future__ import annotations

from vizier.core.agents.architect.prompts import ARCHITECT_CORE_PROMPT, ArchitectPromptAssembler


class TestArchitectCorePrompt:
    def test_contains_role(self) -> None:
        assert "Architect agent" in ARCHITECT_CORE_PROMPT

    def test_mentions_propose_plan(self) -> None:
        assert "PROPOSE_PLAN" in ARCHITECT_CORE_PROMPT

    def test_mentions_depends_on(self) -> None:
        assert "depends_on" in ARCHITECT_CORE_PROMPT

    def test_mentions_write_set(self) -> None:
        assert "write-set" in ARCHITECT_CORE_PROMPT.lower() or "write_set" in ARCHITECT_CORE_PROMPT

    def test_mentions_request_more_research(self) -> None:
        assert "request_more_research" in ARCHITECT_CORE_PROMPT

    def test_lists_all_tools(self) -> None:
        for tool in [
            "read_file",
            "glob",
            "grep",
            "create_spec",
            "read_spec",
            "update_spec_status",
            "send_message",
            "ping_supervisor",
        ]:
            assert tool in ARCHITECT_CORE_PROMPT

    def test_mentions_complexity(self) -> None:
        assert "complexity" in ARCHITECT_CORE_PROMPT.lower()


class TestArchitectPromptAssembler:
    def test_core_only(self) -> None:
        assembler = ArchitectPromptAssembler()
        prompt = assembler.assemble()
        assert "Architect agent" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = ArchitectPromptAssembler()
        assert assembler.core_prompt == ARCHITECT_CORE_PROMPT

    def test_with_learnings(self) -> None:
        assembler = ArchitectPromptAssembler(learnings="Avoid circular imports in models")
        prompt = assembler.assemble()
        assert "Project Learnings" in prompt
        assert "circular imports" in prompt

    def test_without_learnings(self) -> None:
        assembler = ArchitectPromptAssembler()
        prompt = assembler.assemble()
        assert "Project Learnings" not in prompt

    def test_with_architect_guide(self) -> None:
        assembler = ArchitectPromptAssembler(architect_guide="Use feature -> tests pattern")
        prompt = assembler.assemble()
        assert "Plugin Decomposition Patterns" in prompt
        assert "feature -> tests" in prompt

    def test_without_architect_guide(self) -> None:
        assembler = ArchitectPromptAssembler()
        prompt = assembler.assemble()
        assert "Plugin Decomposition Patterns" not in prompt

    def test_both_modules(self) -> None:
        assembler = ArchitectPromptAssembler(
            learnings="Watch out for race conditions",
            architect_guide="Decompose into layers",
        )
        prompt = assembler.assemble()
        assert "race conditions" in prompt
        assert "Decompose into layers" in prompt
        assert prompt.index("Architect agent") < prompt.index("race conditions")
