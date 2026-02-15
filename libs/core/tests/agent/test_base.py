"""Tests for BaseAgent with mocked LLM calls."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vizier.core.agent.base import BaseAgent
from vizier.core.agent.context import AgentContext
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.models.spec import Spec, SpecFrontmatter


class StubAgent(BaseAgent):
    @property
    def role(self) -> str:
        return "worker"

    def build_prompt(self) -> str:
        return f"Do the thing for {self.context.spec.frontmatter.id}" if self.context.spec else "Do something"

    def process_response(self, response) -> str:
        return "REVIEW"


def _make_llm_response(content: str = "Done") -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=50)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture
def context_with_spec() -> AgentContext:
    spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="# Test")
    return AgentContext(project_root="/tmp/test", spec=spec, config={"project": "test-project"})


@pytest.fixture
def context_no_spec() -> AgentContext:
    return AgentContext(project_root="/tmp/test")


class TestBaseAgent:
    def test_run_calls_llm(self, context_with_spec) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response())
        agent = StubAgent(context_with_spec, llm_callable=mock_llm)
        result = agent.run()
        assert result == "REVIEW"
        mock_llm.assert_called_once()

    def test_run_without_llm_raises(self, context_with_spec) -> None:
        agent = StubAgent(context_with_spec)
        with pytest.raises(RuntimeError, match="No LLM callable"):
            agent.run()

    def test_run_logs_entry(self, context_with_spec, tmp_path) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response())
        logger = AgentLogger(tmp_path / "agent-log.jsonl")
        agent = StubAgent(context_with_spec, logger=logger, llm_callable=mock_llm)
        agent.run()
        entries = logger.read_entries()
        assert len(entries) == 1
        assert entries[0].agent == "worker"
        assert entries[0].spec_id == "001-test"
        assert entries[0].result == "REVIEW"

    def test_resolve_model(self, context_with_spec) -> None:
        agent = StubAgent(context_with_spec)
        model = agent.resolve_model()
        assert "sonnet" in model

    def test_build_prompt_uses_spec(self, context_with_spec) -> None:
        agent = StubAgent(context_with_spec)
        prompt = agent.build_prompt()
        assert "001-test" in prompt

    def test_fresh_context_per_invocation(self) -> None:
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="# Test")
        ctx1 = AgentContext(project_root="/tmp/test", spec=spec)
        ctx2 = AgentContext(project_root="/tmp/test", spec=spec)
        agent1 = StubAgent(ctx1)
        agent2 = StubAgent(ctx2)
        assert agent1.context is not agent2.context
