"""Tests for sentinel policy models."""

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest


class TestToolCallRequest:
    def test_minimal(self) -> None:
        req = ToolCallRequest(tool="bash")
        assert req.tool == "bash"
        assert req.args == {}
        assert req.command == ""

    def test_with_command(self) -> None:
        req = ToolCallRequest(tool="bash", command="git status", agent_role="worker", spec_id="001-test")
        assert req.command == "git status"
        assert req.agent_role == "worker"


class TestSentinelResult:
    def test_allow(self) -> None:
        result = SentinelResult(decision=PolicyDecision.ALLOW, reason="safe", policy="allowlist")
        assert result.decision == PolicyDecision.ALLOW
        assert result.cost_usd == 0.0

    def test_deny_with_cost(self) -> None:
        result = SentinelResult(decision=PolicyDecision.DENY, reason="dangerous", policy="haiku", cost_usd=0.001)
        assert result.cost_usd == 0.001
