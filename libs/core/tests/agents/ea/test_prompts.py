"""Tests for EA prompt templates and JIT assembly (D42)."""

from vizier.core.agents.ea.prompts import (
    EA_CORE_PROMPT,
    MODULE_MAP,
    EAPromptAssembler,
    classify_message,
)


class TestClassifyMessage:
    def test_status_command(self) -> None:
        assert classify_message("/status") == "status"

    def test_status_natural(self) -> None:
        assert classify_message("How's everything?") == "status"

    def test_status_keyword(self) -> None:
        assert classify_message("status update please") == "status"

    def test_briefing_command(self) -> None:
        assert classify_message("/briefing") == "briefing"

    def test_briefing_brief(self) -> None:
        assert classify_message("/brief") == "briefing"

    def test_briefing_natural(self) -> None:
        assert classify_message("morning briefing please") == "briefing"

    def test_session_command(self) -> None:
        assert classify_message("/session project-alpha") == "session"

    def test_session_natural(self) -> None:
        assert classify_message("Let's work on project-alpha") == "session"

    def test_checkin_command(self) -> None:
        assert classify_message("/checkin") == "check_in"

    def test_checkin_hyphen(self) -> None:
        assert classify_message("/check-in") == "check_in"

    def test_query_command(self) -> None:
        assert classify_message("/ask project-alpha what's the status?") == "query"

    def test_escalation_keyword(self) -> None:
        assert classify_message("We have a blocker on auth") == "escalation"

    def test_escalation_stuck(self) -> None:
        assert classify_message("The project is stuck") == "escalation"

    def test_delegation_build(self) -> None:
        assert classify_message("Build auth for project-alpha") == "delegation"

    def test_delegation_create(self) -> None:
        assert classify_message("Create a new API endpoint") == "delegation"

    def test_delegation_fix(self) -> None:
        assert classify_message("Fix the login bug") == "delegation"

    def test_delegation_default(self) -> None:
        assert classify_message("hello there") == "delegation"

    def test_approve_command(self) -> None:
        assert classify_message("/approve 001-auth") == "delegation"


class TestEAPromptAssembler:
    def test_core_prompt_always_included(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("Build something")
        assert "Executive Assistant" in prompt
        assert "DRAFT spec seeds" in prompt

    def test_delegation_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("Build auth for project-alpha")
        assert "Delegation Context" in prompt

    def test_status_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("/status")
        assert "Status Report Context" in prompt

    def test_briefing_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("/briefing")
        assert "Briefing Context" in prompt

    def test_session_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("Let's work on project-alpha")
        assert "Session Context" in prompt

    def test_checkin_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("/checkin")
        assert "Check-in Context" in prompt

    def test_escalation_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("We have a blocker")
        assert "Escalation Context" in prompt

    def test_query_module_loaded(self) -> None:
        assembler = EAPromptAssembler()
        prompt = assembler.assemble("/ask project-alpha what's up?")
        assert "Query Context" in prompt

    def test_project_summary_appended(self) -> None:
        assembler = EAPromptAssembler(project_summary="Project Alpha uses pytest")
        prompt = assembler.assemble("Build something")
        assert "Project Capabilities" in prompt
        assert "Project Alpha uses pytest" in prompt

    def test_priorities_appended(self) -> None:
        assembler = EAPromptAssembler(priorities="1. Ship auth by Friday")
        prompt = assembler.assemble("Build something")
        assert "Sultan's Current Priorities" in prompt
        assert "Ship auth by Friday" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = EAPromptAssembler()
        assert assembler.core_prompt == EA_CORE_PROMPT

    def test_all_modules_referenced(self) -> None:
        expected_keys = {"delegation", "status", "briefing", "session", "check_in", "escalation", "query"}
        assert set(MODULE_MAP.keys()) == expected_keys
