"""Tests for tool registry with Sentinel integration."""

from unittest.mock import MagicMock

from vizier.core.plugins.tool_registry import ToolRegistry
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest


class TestToolRegistry:
    def test_disallowed_tool_denied(self) -> None:
        registry = ToolRegistry(allowed_tools=["file_read", "file_write"])
        req = ToolCallRequest(tool="bash", command="echo hello")
        result = registry.check(req)
        assert result.decision == PolicyDecision.DENY
        assert "not in worker's allowed list" in result.reason

    def test_allowed_tool_without_sentinel(self) -> None:
        registry = ToolRegistry(allowed_tools=["file_read"])
        req = ToolCallRequest(tool="file_read")
        result = registry.check(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_restriction_denied_pattern(self) -> None:
        registry = ToolRegistry(
            allowed_tools=["bash"],
            tool_restrictions={"bash": {"denied_patterns": [r"rm -rf.*"]}},
        )
        req = ToolCallRequest(tool="bash", command="rm -rf /tmp")
        result = registry.check(req)
        assert result.decision == PolicyDecision.DENY

    def test_restriction_allowed_pattern(self) -> None:
        registry = ToolRegistry(
            allowed_tools=["bash"],
            tool_restrictions={"bash": {"allowed_patterns": [r"uv run pytest.*"]}},
        )
        req = ToolCallRequest(tool="bash", command="uv run pytest -v")
        result = registry.check(req)
        assert result.decision == PolicyDecision.ALLOW

    def test_restriction_no_match_denied(self) -> None:
        registry = ToolRegistry(
            allowed_tools=["bash"],
            tool_restrictions={"bash": {"allowed_patterns": [r"uv run pytest.*"]}},
        )
        req = ToolCallRequest(tool="bash", command="curl http://example.com")
        result = registry.check(req)
        assert result.decision == PolicyDecision.DENY
        assert "does not match any allowed pattern" in result.reason

    def test_sentinel_integration(self) -> None:
        mock_sentinel = MagicMock()
        mock_sentinel.evaluate.return_value = SentinelResult(
            decision=PolicyDecision.ALLOW, reason="Sentinel approved", policy="allowlist"
        )
        registry = ToolRegistry(allowed_tools=["bash"], sentinel=mock_sentinel)
        req = ToolCallRequest(tool="bash", command="echo hello")
        result = registry.check(req)
        assert result.decision == PolicyDecision.ALLOW
        mock_sentinel.evaluate.assert_called_once()

    def test_sentinel_deny_overrides(self) -> None:
        mock_sentinel = MagicMock()
        mock_sentinel.evaluate.return_value = SentinelResult(
            decision=PolicyDecision.DENY, reason="Sentinel denied", policy="denylist"
        )
        registry = ToolRegistry(allowed_tools=["bash"], sentinel=mock_sentinel)
        req = ToolCallRequest(tool="bash", command="suspicious_command")
        result = registry.check(req)
        assert result.decision == PolicyDecision.DENY

    def test_restriction_check_before_sentinel(self) -> None:
        mock_sentinel = MagicMock()
        registry = ToolRegistry(
            allowed_tools=["bash"],
            tool_restrictions={"bash": {"denied_patterns": [r"rm -rf.*"]}},
            sentinel=mock_sentinel,
        )
        req = ToolCallRequest(tool="bash", command="rm -rf /tmp")
        result = registry.check(req)
        assert result.decision == PolicyDecision.DENY
        mock_sentinel.evaluate.assert_not_called()
