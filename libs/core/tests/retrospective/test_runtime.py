"""Tests for Retrospective runtime."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vizier.core.agent.context import AgentContext
from vizier.core.retrospective.runtime import (
    RetrospectiveRuntime,
    _parse_learnings,
    _parse_proposals,
)


def _setup_project(tmp_path: Path) -> Path:
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    (vizier_dir / "constitution.md").write_text("Test constitution.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("# Learnings\n\nNo learnings yet.", encoding="utf-8")
    (vizier_dir / "config.yaml").write_text("plugin: software\nproject: test-project\n", encoding="utf-8")
    (vizier_dir / "state.json").write_text(
        json.dumps({"project": "test-project", "plugin": "software"}),
        encoding="utf-8",
    )
    return tmp_path


def _make_llm_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    return _setup_project(tmp_path)


@pytest.fixture
def context(project_root: Path) -> AgentContext:
    return AgentContext.load_from_disk(str(project_root))


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


class TestParseLearnings:
    def test_parse_single(self) -> None:
        content = "LEARNING: Always validate input types before processing"
        learnings = _parse_learnings(content)
        assert len(learnings) == 1
        assert learnings[0] == "Always validate input types before processing"

    def test_parse_multiple(self) -> None:
        content = "Some text\nLEARNING: First insight\nMore text\nLEARNING: Second insight\n"
        learnings = _parse_learnings(content)
        assert len(learnings) == 2

    def test_case_insensitive(self) -> None:
        content = "learning: lowercase works too"
        learnings = _parse_learnings(content)
        assert len(learnings) == 1

    def test_empty_learning_skipped(self) -> None:
        content = "LEARNING: \nLEARNING: real insight"
        learnings = _parse_learnings(content)
        assert len(learnings) == 1

    def test_no_learnings(self) -> None:
        content = "No special markers here"
        learnings = _parse_learnings(content)
        assert len(learnings) == 0


class TestParseProposals:
    def test_parse_single_proposal(self) -> None:
        content = (
            "PROPOSAL: Add type checking to worker prompts\n"
            "TYPE: prompt_change\n"
            "DESCRIPTION: Workers should be reminded to add type annotations\n"
            "RATIONALE: 40% of rejections cite missing types\n"
        )
        proposals = _parse_proposals(content)
        assert len(proposals) == 1
        title, body = proposals[0]
        assert title == "Add type checking to worker prompts"
        assert "prompt_change" in body

    def test_parse_multiple_proposals(self) -> None:
        content = "PROPOSAL: First change\nDESCRIPTION: Details 1\nPROPOSAL: Second change\nDESCRIPTION: Details 2\n"
        proposals = _parse_proposals(content)
        assert len(proposals) == 2

    def test_no_proposals(self) -> None:
        content = "Just regular text"
        proposals = _parse_proposals(content)
        assert len(proposals) == 0

    def test_empty_title_skipped(self) -> None:
        content = "PROPOSAL: \nDESCRIPTION: orphaned\n"
        proposals = _parse_proposals(content)
        assert len(proposals) == 0


class TestRetrospectiveRuntime:
    def test_role(self, context: AgentContext, mock_llm: MagicMock) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        assert runtime.role == "retrospective"

    def test_build_prompt(self, context: AgentContext, mock_llm: MagicMock) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        prompt = runtime.build_prompt()
        assert "Retrospective" in prompt
        assert "learnings" in prompt.lower()
        assert "Metrics" in prompt

    def test_process_response_with_learnings(
        self, context: AgentContext, mock_llm: MagicMock, project_root: Path
    ) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)

        response = _make_llm_response("LEARNING: Workers should validate file existence before editing")
        result = runtime.process_response(response)

        assert "1 learning" in result
        assert len(runtime.learnings_added) == 1

        learnings_path = project_root / ".vizier" / "learnings.md"
        content = learnings_path.read_text(encoding="utf-8")
        assert "validate file existence" in content

    def test_process_response_with_proposals(
        self, context: AgentContext, mock_llm: MagicMock, project_root: Path
    ) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)

        response = _make_llm_response(
            "PROPOSAL: Add file existence criteria\n"
            "TYPE: criteria_change\n"
            "DESCRIPTION: New @criteria/file_exists check\n"
        )
        result = runtime.process_response(response)

        assert "1 proposal" in result
        assert len(runtime.proposals_written) == 1

        proposals_dir = project_root / ".vizier" / "proposals"
        assert proposals_dir.exists()
        proposal_files = list(proposals_dir.glob("*.md"))
        assert len(proposal_files) == 1

        content = proposal_files[0].read_text(encoding="utf-8")
        assert "PENDING" in content
        assert "Sultan approval" in content

    def test_process_response_no_changes(self, context: AgentContext, mock_llm: MagicMock) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        response = _make_llm_response("Everything looks good, no changes needed.")
        result = runtime.process_response(response)
        assert "no changes needed" in result

    def test_full_run(self, context: AgentContext, project_root: Path) -> None:
        mock_llm = MagicMock()
        mock_llm.return_value = _make_llm_response(
            "LEARNING: Specs with >3 artifacts tend to fail\n"
            "PROPOSAL: Limit artifacts per spec\n"
            "TYPE: process_change\n"
            "DESCRIPTION: Cap at 3 artifacts per spec\n"
        )

        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        result = runtime.run_analysis()

        assert "RETROSPECTIVE" in result
        assert len(runtime.learnings_added) == 1
        assert len(runtime.proposals_written) == 1

    def test_learnings_append_not_overwrite(
        self, context: AgentContext, mock_llm: MagicMock, project_root: Path
    ) -> None:
        learnings_path = project_root / ".vizier" / "learnings.md"
        original = learnings_path.read_text(encoding="utf-8")

        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        response = _make_llm_response("LEARNING: New insight here")
        runtime.process_response(response)

        updated = learnings_path.read_text(encoding="utf-8")
        assert original.strip() in updated
        assert "New insight here" in updated

    def test_no_tmp_files_left(self, context: AgentContext, mock_llm: MagicMock, project_root: Path) -> None:
        runtime = RetrospectiveRuntime(context=context, llm_callable=mock_llm)
        response = _make_llm_response("LEARNING: Test insight\nPROPOSAL: Test proposal\nDESCRIPTION: Details\n")
        runtime.process_response(response)

        tmp_files = list(Path(project_root).rglob("*.tmp"))
        assert len(tmp_files) == 0


class TestAgentRunnerIntegration:
    def test_run_retrospective(self, project_root: Path) -> None:
        from vizier.core.agent_runner.runner import AgentRunner

        mock_llm = MagicMock()
        mock_llm.return_value = _make_llm_response("LEARNING: Integration test insight")

        runner = AgentRunner(
            project_root=str(project_root),
            llm_callable=mock_llm,
        )
        result = runner.run_retrospective()
        assert result.agent_type == "retrospective"
        assert result.error == ""
        assert "RETROSPECTIVE" in result.result
