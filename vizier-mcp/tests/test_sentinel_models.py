"""Tests for Sentinel Pydantic models."""

from __future__ import annotations

from vizier_mcp.models.sentinel import (
    CommandCheckResult,
    DenylistEntry,
    HaikuVerdict,
    PolicyDecision,
    RolePermissions,
    SentinelPolicy,
    WebFetchResult,
)


class TestPolicyDecision:
    """Tests for PolicyDecision enum."""

    def test_values(self) -> None:
        assert PolicyDecision.ALLOW == "ALLOW"
        assert PolicyDecision.DENY == "DENY"
        assert PolicyDecision.ABSTAIN == "ABSTAIN"

    def test_is_str_enum(self) -> None:
        assert isinstance(PolicyDecision.ALLOW, str)


class TestDenylistEntry:
    """Tests for DenylistEntry model."""

    def test_with_reason(self) -> None:
        entry = DenylistEntry(pattern="rm -rf", reason="Destructive command")
        assert entry.pattern == "rm -rf"
        assert entry.reason == "Destructive command"

    def test_default_reason(self) -> None:
        entry = DenylistEntry(pattern="sudo")
        assert entry.reason == "Denied by policy"


class TestRolePermissions:
    """Tests for RolePermissions model."""

    def test_defaults(self) -> None:
        perms = RolePermissions()
        assert perms.can_write is True
        assert perms.can_bash is True
        assert perms.can_read is True

    def test_restricted(self) -> None:
        perms = RolePermissions(can_write=False, can_bash=False)
        assert perms.can_write is False
        assert perms.can_bash is False
        assert perms.can_read is True


class TestSentinelPolicy:
    """Tests for SentinelPolicy model."""

    def test_defaults(self) -> None:
        policy = SentinelPolicy()
        assert policy.write_set == []
        assert policy.command_allowlist == []
        assert policy.command_denylist == []
        assert policy.role_permissions == {}

    def test_with_data(self) -> None:
        policy = SentinelPolicy(
            write_set=["src/**/*.py"],
            command_allowlist=["pytest"],
            command_denylist=["rm -rf", DenylistEntry(pattern="sudo", reason="No sudo")],
            role_permissions={"worker": RolePermissions(can_bash=True)},
        )
        assert len(policy.write_set) == 1
        assert len(policy.command_allowlist) == 1
        assert len(policy.command_denylist) == 2
        assert "worker" in policy.role_permissions


class TestCommandCheckResult:
    """Tests for CommandCheckResult model (D78 shapes)."""

    def test_denied_shape(self) -> None:
        result = CommandCheckResult(allowed=False, reason="Denied by policy")
        assert result.allowed is False
        assert result.reason == "Denied by policy"
        assert result.exit_code is None

    def test_succeeded_shape(self) -> None:
        result = CommandCheckResult(allowed=True, exit_code=0, stdout="ok", stderr="")
        assert result.allowed is True
        assert result.exit_code == 0
        assert result.stdout == "ok"

    def test_failed_shape(self) -> None:
        result = CommandCheckResult(allowed=True, exit_code=1, stdout="", stderr="error")
        assert result.allowed is True
        assert result.exit_code == 1
        assert result.stderr == "error"


class TestWebFetchResult:
    """Tests for WebFetchResult model (D78 shapes)."""

    def test_blocked_shape(self) -> None:
        result = WebFetchResult(safe=False, reason="Injection detected")
        assert result.safe is False
        assert result.reason == "Injection detected"

    def test_fetched_shape(self) -> None:
        result = WebFetchResult(safe=True, content="hello", status_code=200)
        assert result.safe is True
        assert result.content == "hello"

    def test_failed_shape(self) -> None:
        result = WebFetchResult(safe=True, content="", status_code=404, error="Not found")
        assert result.safe is True
        assert result.status_code == 404
        assert result.error == "Not found"


class TestHaikuVerdict:
    """Tests for HaikuVerdict model."""

    def test_allow_verdict(self) -> None:
        verdict = HaikuVerdict(decision=PolicyDecision.ALLOW, reason="Safe command")
        assert verdict.decision == PolicyDecision.ALLOW
        assert verdict.cost_usd == 0.0

    def test_deny_verdict(self) -> None:
        verdict = HaikuVerdict(decision=PolicyDecision.DENY, reason="Dangerous", cost_usd=0.001)
        assert verdict.decision == PolicyDecision.DENY
        assert verdict.cost_usd == 0.001

    def test_serialization(self) -> None:
        verdict = HaikuVerdict(decision=PolicyDecision.ALLOW, reason="ok")
        data = verdict.model_dump(mode="json")
        assert data["decision"] == "ALLOW"
        assert data["reason"] == "ok"
