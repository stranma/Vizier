"""Tests for Pasha system prompt templates."""

from vizier.core.agents.pasha.prompts import (
    MODULE_MAP,
    PASHA_CORE_PROMPT,
    PashaPromptAssembler,
)


class TestPashaPromptAssembler:
    def test_core_prompt_included(self) -> None:
        assembler = PashaPromptAssembler()
        prompt = assembler.assemble()
        assert "Pasha" in prompt
        assert "orchestrator" in prompt
        assert "Spec Lifecycle" in prompt

    def test_session_module(self) -> None:
        assembler = PashaPromptAssembler()
        prompt = assembler.assemble("session")
        assert "Session Mode" in prompt

    def test_reconciliation_module(self) -> None:
        assembler = PashaPromptAssembler()
        prompt = assembler.assemble("reconciliation")
        assert "Reconciliation Context" in prompt

    def test_no_module(self) -> None:
        assembler = PashaPromptAssembler()
        prompt = assembler.assemble("")
        assert "Session Mode" not in prompt
        assert "Reconciliation Context" not in prompt

    def test_project_name_included(self) -> None:
        assembler = PashaPromptAssembler(project_name="alpha")
        prompt = assembler.assemble()
        assert "Project: alpha" in prompt

    def test_project_context_included(self) -> None:
        assembler = PashaPromptAssembler(project_context="This project uses FastAPI.")
        prompt = assembler.assemble()
        assert "FastAPI" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = PashaPromptAssembler()
        assert assembler.core_prompt == PASHA_CORE_PROMPT

    def test_all_modules(self) -> None:
        assert set(MODULE_MAP.keys()) == {"session", "reconciliation"}
