"""Tests for Scout prompt assembly."""

from __future__ import annotations

from vizier.core.agents.scout.prompts import SCOUT_CORE_PROMPT, ScoutPromptAssembler


class TestScoutCorePrompt:
    def test_contains_role(self) -> None:
        assert "Scout agent" in SCOUT_CORE_PROMPT

    def test_contains_research_process(self) -> None:
        assert "Research Process" in SCOUT_CORE_PROMPT

    def test_mentions_llm_judgment(self) -> None:
        assert "LLM judgment" in SCOUT_CORE_PROMPT

    def test_no_keyword_patterns(self) -> None:
        assert "keyword" not in SCOUT_CORE_PROMPT.lower() or "no keyword" in SCOUT_CORE_PROMPT.lower()

    def test_mentions_confidence(self) -> None:
        assert "confidence" in SCOUT_CORE_PROMPT.lower()

    def test_mentions_research_report(self) -> None:
        assert "RESEARCH_REPORT" in SCOUT_CORE_PROMPT

    def test_lists_tools(self) -> None:
        assert "read_file" in SCOUT_CORE_PROMPT
        assert "bash" in SCOUT_CORE_PROMPT
        assert "update_spec_status" in SCOUT_CORE_PROMPT
        assert "send_message" in SCOUT_CORE_PROMPT


class TestScoutPromptAssembler:
    def test_core_only(self) -> None:
        assembler = ScoutPromptAssembler()
        prompt = assembler.assemble()
        assert "Scout agent" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = ScoutPromptAssembler()
        assert assembler.core_prompt == SCOUT_CORE_PROMPT

    def test_with_plugin_guide(self) -> None:
        assembler = ScoutPromptAssembler(plugin_guide="Check PyPI for existing packages")
        prompt = assembler.assemble()
        assert "Plugin Research Guide" in prompt
        assert "Check PyPI" in prompt

    def test_without_plugin_guide(self) -> None:
        assembler = ScoutPromptAssembler()
        prompt = assembler.assemble()
        assert "Plugin Research Guide" not in prompt

    def test_plugin_guide_appended(self) -> None:
        assembler = ScoutPromptAssembler(plugin_guide="Always search npm registry")
        prompt = assembler.assemble()
        assert prompt.index("Scout agent") < prompt.index("npm registry")
