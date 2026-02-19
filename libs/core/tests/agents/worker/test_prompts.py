"""Tests for Worker prompt assembly."""

from __future__ import annotations

from vizier.core.agents.worker.prompts import WORKER_CORE_PROMPT, WorkerPromptAssembler


class TestWorkerCorePrompt:
    def test_contains_role(self) -> None:
        assert "Worker agent" in WORKER_CORE_PROMPT

    def test_mentions_fresh_context(self) -> None:
        assert "fresh" in WORKER_CORE_PROMPT.lower()

    def test_mentions_write_set(self) -> None:
        assert "write-set" in WORKER_CORE_PROMPT.lower() or "Write-set" in WORKER_CORE_PROMPT

    def test_mentions_sentinel(self) -> None:
        assert "Sentinel" in WORKER_CORE_PROMPT

    def test_mentions_clarification(self) -> None:
        assert "REQUEST_CLARIFICATION" in WORKER_CORE_PROMPT

    def test_mentions_ping_supervisor(self) -> None:
        assert "ping_supervisor" in WORKER_CORE_PROMPT

    def test_lists_all_tools(self) -> None:
        for tool in [
            "read_file",
            "write_file",
            "edit_file",
            "bash",
            "glob",
            "grep",
            "git",
            "run_tests",
            "escalate_to_pasha",
            "update_spec_status",
            "write_feedback",
            "send_message",
            "ping_supervisor",
        ]:
            assert tool in WORKER_CORE_PROMPT

    def test_mentions_review_status(self) -> None:
        assert "REVIEW" in WORKER_CORE_PROMPT


class TestWorkerPromptAssembler:
    def test_core_only(self) -> None:
        assembler = WorkerPromptAssembler()
        prompt = assembler.assemble()
        assert "Worker agent" in prompt

    def test_core_prompt_property(self) -> None:
        assembler = WorkerPromptAssembler()
        assert assembler.core_prompt == WORKER_CORE_PROMPT

    def test_with_spec_context(self) -> None:
        assembler = WorkerPromptAssembler(
            goal="Add JWT authentication",
            constraints="Use PyJWT library",
            acceptance_criteria="All auth tests pass",
            write_set="src/auth/**/*.py, tests/auth/**/*.py",
            complexity="HIGH",
        )
        prompt = assembler.assemble()
        assert "JWT authentication" in prompt
        assert "PyJWT" in prompt
        assert "auth tests pass" in prompt
        assert "src/auth" in prompt
        assert "HIGH" in prompt

    def test_without_spec_context(self) -> None:
        assembler = WorkerPromptAssembler()
        prompt = assembler.assemble()
        assert "Current Spec" not in prompt

    def test_with_learnings(self) -> None:
        assembler = WorkerPromptAssembler(
            goal="Add feature",
            learnings="Always run type checker before committing",
        )
        prompt = assembler.assemble()
        assert "Relevant Learnings" in prompt
        assert "type checker" in prompt

    def test_without_learnings(self) -> None:
        assembler = WorkerPromptAssembler(goal="Add feature")
        prompt = assembler.assemble()
        assert "Relevant Learnings" not in prompt

    def test_with_worker_guide(self) -> None:
        assembler = WorkerPromptAssembler(
            goal="Implement endpoint",
            worker_guide="Use FastAPI router pattern",
        )
        prompt = assembler.assemble()
        assert "Plugin Worker Guide" in prompt
        assert "FastAPI" in prompt

    def test_without_worker_guide(self) -> None:
        assembler = WorkerPromptAssembler(goal="Implement endpoint")
        prompt = assembler.assemble()
        assert "Plugin Worker Guide" not in prompt

    def test_all_modules(self) -> None:
        assembler = WorkerPromptAssembler(
            goal="Build API",
            constraints="Use REST",
            acceptance_criteria="Tests pass",
            write_set="src/**",
            complexity="MEDIUM",
            learnings="Check for N+1 queries",
            worker_guide="Follow layered architecture",
        )
        prompt = assembler.assemble()
        assert "Build API" in prompt
        assert "N+1 queries" in prompt
        assert "layered architecture" in prompt

    def test_ordering(self) -> None:
        assembler = WorkerPromptAssembler(
            goal="Build API",
            learnings="Use async",
            worker_guide="Layer pattern",
        )
        prompt = assembler.assemble()
        assert prompt.index("Worker agent") < prompt.index("Build API")
        assert prompt.index("Build API") < prompt.index("Use async")
        assert prompt.index("Use async") < prompt.index("Layer pattern")
