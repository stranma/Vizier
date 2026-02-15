"""Tests for Haiku evaluator (mocked LLM calls)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from vizier.core.sentinel.haiku_evaluator import HaikuEvaluator
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest


def _make_llm_response(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_cost=0.001)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestHaikuEvaluator:
    def test_allows_safe_command(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("ALLOW"))
        evaluator = HaikuEvaluator(mock_llm)
        req = ToolCallRequest(tool="bash", command="echo hello", agent_role="worker", spec_id="001-test")
        result = evaluator.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
        mock_llm.assert_called_once()

    def test_denies_dangerous_command(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("DENY"))
        evaluator = HaikuEvaluator(mock_llm)
        # Simulate an indirect destructive command via subprocess wrapper
        req = ToolCallRequest(
            tool="bash",
            command='python -c \'import subprocess; subprocess.run(["rm", "-rf", "/tmp"])\'',
            agent_role="worker",
        )
        result = evaluator.evaluate(req)
        assert result.decision == PolicyDecision.DENY

    def test_denies_on_llm_failure(self) -> None:
        mock_llm = MagicMock(side_effect=Exception("API error"))
        evaluator = HaikuEvaluator(mock_llm)
        req = ToolCallRequest(tool="bash", command="some command")
        result = evaluator.evaluate(req)
        assert result.decision == PolicyDecision.DENY
        assert "fail-closed" in result.reason

    def test_extracts_cost(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("ALLOW"))
        evaluator = HaikuEvaluator(mock_llm)
        req = ToolCallRequest(tool="bash", command="test")
        result = evaluator.evaluate(req)
        assert result.cost_usd == 0.001

    def test_uses_command_from_args(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("ALLOW"))
        evaluator = HaikuEvaluator(mock_llm)
        req = ToolCallRequest(tool="bash", args={"command": "echo test"})
        result = evaluator.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
