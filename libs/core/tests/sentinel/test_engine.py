"""Tests for the SentinelEngine pipeline."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest


def _make_llm_response(content: str) -> SimpleNamespace:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(total_cost=0.001)
    return SimpleNamespace(choices=[choice], usage=usage)


class TestSentinelEngine:
    def test_allowlist_short_circuits(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="read_file")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
        assert result.policy == "allowlist"

    def test_denylist_short_circuits(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="rm -rf /")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY
        assert result.policy == "denylist"

    def test_secret_scanner_blocks(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="export ANTHROPIC_API_KEY=sk-ant-secret123")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY
        assert result.policy == "secret_scanner"

    def test_git_classifier_allows_safe(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="git status")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_git_classifier_denies_dangerous(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="git push --force origin main")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY

    def test_haiku_called_for_ambiguous(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("ALLOW"))
        engine = SentinelEngine(llm_callable=mock_llm)
        req = ToolCallRequest(tool="bash", command="some_unfamiliar_command --weird-flag")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
        assert result.policy == "haiku_evaluator"
        mock_llm.assert_called_once()

    def test_haiku_denies_indirect_destructive(self) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("DENY"))
        engine = SentinelEngine(llm_callable=mock_llm)
        # Indirect destructive command wrapped in python subprocess
        req = ToolCallRequest(
            tool="bash",
            command='python -c \'import subprocess; subprocess.run(["rm", "-rf", "/tmp"])\'',
            agent_role="worker",
        )
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY

    def test_no_haiku_fails_closed(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="some_unknown_command")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY
        assert "fail-closed" in result.reason

    def test_pipeline_order_denylist_before_secret(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="bash", command="rm -rf / ANTHROPIC_API_KEY=secret")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.DENY
        assert result.policy == "denylist"

    def test_allowlist_before_denylist(self) -> None:
        engine = SentinelEngine()
        req = ToolCallRequest(tool="read_file")
        result = engine.evaluate(req)
        assert result.decision == PolicyDecision.ALLOW
        assert result.policy == "allowlist"
