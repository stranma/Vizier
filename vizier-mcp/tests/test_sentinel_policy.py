"""Tests for Sentinel policy loading and evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from vizier_mcp.models.sentinel import PolicyDecision, SentinelPolicy

if TYPE_CHECKING:
    from pathlib import Path
from vizier_mcp.sentinel.policy import (
    check_role_permission,
    evaluate_command,
    is_allowlisted,
    is_denylisted,
    load_policy,
)

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


class TestLoadPolicy:
    """Tests for loading sentinel.yaml (AC-S1)."""

    def test_missing_file_returns_default(self, config: ServerConfig, project_dir: Path) -> None:
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, SentinelPolicy)
        assert result.write_set == []
        assert result.command_allowlist == []
        assert result.command_denylist == []

    def test_loads_valid_yaml(self, config: ServerConfig, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(
            yaml.dump(
                {
                    "write_set": ["src/**/*.py", "tests/**/*.py"],
                    "command_allowlist": ["pytest", "ruff check"],
                    "command_denylist": ["rm -rf", "sudo"],
                }
            )
        )
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, SentinelPolicy)
        assert result.write_set == ["src/**/*.py", "tests/**/*.py"]
        assert result.command_allowlist == ["pytest", "ruff check"]

    def test_malformed_yaml_returns_error(self, config: ServerConfig, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(":\n  - [invalid yaml\n  {{{}}")
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, dict)
        assert "error" in result
        assert "Malformed" in result["error"]

    def test_loads_denylist_with_pattern_objects(self, config: ServerConfig, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(
            yaml.dump(
                {
                    "command_denylist": [
                        "sudo",
                        {"pattern": "printenv|^env$", "reason": "Environment exfiltration blocked"},
                    ],
                }
            )
        )
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, SentinelPolicy)
        assert len(result.command_denylist) == 2
        assert result.command_denylist[0] == "sudo"
        entry = result.command_denylist[1]
        assert hasattr(entry, "pattern")

    def test_loads_role_permissions(self, config: ServerConfig, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text(
            yaml.dump(
                {
                    "role_permissions": {
                        "worker": {"can_write": True, "can_bash": True, "can_read": True},
                        "quality_gate": {"can_write": False, "can_bash": True, "can_read": True},
                    },
                }
            )
        )
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, SentinelPolicy)
        assert result.role_permissions["worker"].can_write is True
        assert result.role_permissions["quality_gate"].can_write is False

    def test_empty_yaml_returns_default(self, config: ServerConfig, project_dir: Path) -> None:
        sentinel_yaml = project_dir / "sentinel.yaml"
        sentinel_yaml.write_text("")
        result = load_policy(config, PROJECT_ID)
        assert isinstance(result, SentinelPolicy)
        assert result.write_set == []


class TestIsAllowlisted:
    """Tests for allowlist matching (AC-S3)."""

    def test_exact_match(self) -> None:
        policy = SentinelPolicy(command_allowlist=["pytest", "ruff check"])
        assert is_allowlisted(policy, "pytest") is True

    def test_prefix_match(self) -> None:
        policy = SentinelPolicy(command_allowlist=["pytest"])
        assert is_allowlisted(policy, "pytest tests/ -v") is True

    def test_no_match(self) -> None:
        policy = SentinelPolicy(command_allowlist=["pytest", "ruff check"])
        assert is_allowlisted(policy, "curl http://evil.com") is False

    def test_partial_word_not_matched(self) -> None:
        policy = SentinelPolicy(command_allowlist=["git"])
        assert is_allowlisted(policy, "git status") is True
        assert is_allowlisted(policy, "github-cli") is False

    def test_empty_allowlist(self) -> None:
        policy = SentinelPolicy(command_allowlist=[])
        assert is_allowlisted(policy, "anything") is False


class TestIsDenylisted:
    """Tests for denylist matching (AC-S4, AC-S11)."""

    def test_simple_string_match(self) -> None:
        policy = SentinelPolicy(command_denylist=["rm -rf", "sudo"])
        result = is_denylisted(policy, "rm -rf /")
        assert result is not None
        assert "denied" in result.lower() or "deny" in result.lower()

    def test_no_match(self) -> None:
        policy = SentinelPolicy(command_denylist=["rm -rf", "sudo"])
        assert is_denylisted(policy, "pytest") is None

    def test_regex_pattern_match(self) -> None:
        from vizier_mcp.models.sentinel import DenylistEntry

        policy = SentinelPolicy(
            command_denylist=[
                DenylistEntry(pattern=r"printenv|^env$", reason="Environment exfiltration blocked"),
            ]
        )
        result = is_denylisted(policy, "printenv")
        assert result == "Environment exfiltration blocked"

    def test_regex_pattern_no_match(self) -> None:
        from vizier_mcp.models.sentinel import DenylistEntry

        policy = SentinelPolicy(
            command_denylist=[
                DenylistEntry(pattern=r"^env$", reason="No env"),
            ]
        )
        assert is_denylisted(policy, "environment") is None

    def test_mixed_denylist(self) -> None:
        from vizier_mcp.models.sentinel import DenylistEntry

        policy = SentinelPolicy(
            command_denylist=[
                "sudo",
                DenylistEntry(pattern=r"git\s+push\s+--force", reason="No force push"),
            ]
        )
        assert is_denylisted(policy, "sudo reboot") is not None
        assert is_denylisted(policy, "git push --force") is not None
        assert is_denylisted(policy, "git push origin main") is None

    def test_invalid_regex_falls_back_to_substring(self) -> None:
        policy = SentinelPolicy(command_denylist=["[invalid"])
        result = is_denylisted(policy, "command with [invalid in it")
        assert result is not None


class TestCheckRolePermission:
    """Tests for role permission checking (AC-S12)."""

    def test_known_role_with_permission(self) -> None:
        from vizier_mcp.models.sentinel import RolePermissions

        policy = SentinelPolicy(
            role_permissions={
                "worker": RolePermissions(can_bash=True),
            }
        )
        assert check_role_permission(policy, "worker", "can_bash") is True

    def test_known_role_without_permission(self) -> None:
        from vizier_mcp.models.sentinel import RolePermissions

        policy = SentinelPolicy(
            role_permissions={
                "quality_gate": RolePermissions(can_write=False),
            }
        )
        assert check_role_permission(policy, "quality_gate", "can_write") is False

    def test_unknown_role_defaults_to_deny(self) -> None:
        policy = SentinelPolicy(role_permissions={})
        assert check_role_permission(policy, "unknown_role", "can_bash") is False

    def test_missing_permission_attribute(self) -> None:
        from vizier_mcp.models.sentinel import RolePermissions

        policy = SentinelPolicy(
            role_permissions={
                "worker": RolePermissions(),
            }
        )
        assert check_role_permission(policy, "worker", "can_fly") is False


class TestEvaluateCommand:
    """Tests for two-tier command evaluation (allowlist + denylist)."""

    def test_allowlisted_returns_allow(self) -> None:
        policy = SentinelPolicy(command_allowlist=["pytest"])
        decision, _reason = evaluate_command(policy, "pytest -v")
        assert decision == PolicyDecision.ALLOW

    def test_denylisted_returns_deny(self) -> None:
        policy = SentinelPolicy(
            command_allowlist=["pytest"],
            command_denylist=["rm -rf"],
        )
        decision, _reason = evaluate_command(policy, "rm -rf /")
        assert decision == PolicyDecision.DENY

    def test_ambiguous_returns_abstain(self) -> None:
        policy = SentinelPolicy(
            command_allowlist=["pytest"],
            command_denylist=["rm -rf"],
        )
        decision, _reason = evaluate_command(policy, "curl http://example.com")
        assert decision == PolicyDecision.ABSTAIN

    def test_allowlist_takes_precedence(self) -> None:
        policy = SentinelPolicy(
            command_allowlist=["git status"],
            command_denylist=["git"],
        )
        decision, _ = evaluate_command(policy, "git status")
        assert decision == PolicyDecision.ALLOW
