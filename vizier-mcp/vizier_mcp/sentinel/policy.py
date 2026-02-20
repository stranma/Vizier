"""Policy loading and evaluation.

Loads per-project sentinel.yaml and provides the three-tier evaluation:
allowlist -> denylist -> Haiku for commands, and glob matching for write-set.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import yaml

from vizier_mcp.models.sentinel import (
    DenylistEntry,
    PolicyDecision,
    RolePermissions,
    SentinelPolicy,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)


def _sentinel_yaml_path(config: ServerConfig, project_id: str) -> Path:
    """Return the path to a project's sentinel.yaml."""
    assert config.projects_dir is not None
    return config.projects_dir / project_id / "sentinel.yaml"


def load_policy(config: ServerConfig, project_id: str) -> SentinelPolicy | dict:
    """Load SentinelPolicy from a project's sentinel.yaml.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :return: SentinelPolicy on success, or {"error": str} on malformed YAML.
    """
    path = _sentinel_yaml_path(config, project_id)
    if not path.exists():
        return SentinelPolicy()

    try:
        content = path.read_text()
        data = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        return {"error": f"Malformed sentinel.yaml: {exc}"}

    denylist_raw = data.get("command_denylist", [])
    denylist: list[str | DenylistEntry] = []
    for entry in denylist_raw:
        if isinstance(entry, str):
            denylist.append(entry)
        elif isinstance(entry, dict) and "pattern" in entry:
            denylist.append(DenylistEntry(**entry))
        else:
            denylist.append(str(entry))

    role_perms: dict[str, RolePermissions] = {}
    for role, perms in data.get("role_permissions", {}).items():
        role_perms[role] = RolePermissions(**perms)

    return SentinelPolicy(
        write_set=data.get("write_set", []),
        command_allowlist=data.get("command_allowlist", []),
        command_denylist=denylist,
        role_permissions=role_perms,
    )


def check_role_permission(policy: SentinelPolicy, agent_role: str, permission: str) -> bool:
    """Check if an agent role has a specific permission.

    Fail-closed: unknown roles default to deny.

    :param policy: The loaded sentinel policy.
    :param agent_role: The agent's role string.
    :param permission: One of 'can_write', 'can_bash', 'can_read'.
    :return: True if allowed, False if denied.
    """
    if agent_role not in policy.role_permissions:
        return False
    perms = policy.role_permissions[agent_role]
    return bool(getattr(perms, permission, False))


def is_allowlisted(policy: SentinelPolicy, command: str) -> bool:
    """Check if a command matches the allowlist (zero LLM cost).

    Matches if the command starts with any allowlist entry.

    :param policy: The loaded sentinel policy.
    :param command: The shell command string.
    :return: True if the command is allowlisted.
    """
    cmd_stripped = command.strip()
    for pattern in policy.command_allowlist:
        if cmd_stripped == pattern or cmd_stripped.startswith(pattern + " "):
            return True
    return False


def is_denylisted(policy: SentinelPolicy, command: str) -> str | None:
    """Check if a command matches the denylist (zero LLM cost).

    :param policy: The loaded sentinel policy.
    :param command: The shell command string.
    :return: Denial reason if matched, None if not denylisted.
    """
    cmd_stripped = command.strip()
    for entry in policy.command_denylist:
        if isinstance(entry, str):
            if cmd_stripped == entry or cmd_stripped.startswith(entry + " "):
                return f"Command denied by policy: {entry}"
            try:
                if re.search(entry, cmd_stripped):
                    return f"Command matches deny pattern: {entry}"
            except re.error:
                if entry in cmd_stripped:
                    return f"Command contains denied term: {entry}"
        elif isinstance(entry, DenylistEntry):
            try:
                if re.search(entry.pattern, cmd_stripped):
                    return entry.reason
            except re.error:
                logger.warning("Invalid denylist regex: %s", entry.pattern)
                if entry.pattern in cmd_stripped:
                    return entry.reason
    return None


def evaluate_command(policy: SentinelPolicy, command: str) -> tuple[PolicyDecision, str]:
    """Evaluate a command against allowlist and denylist tiers.

    :param policy: The loaded sentinel policy.
    :param command: The shell command string.
    :return: (decision, reason) tuple. ABSTAIN means Haiku should decide.
    """
    if is_allowlisted(policy, command):
        return PolicyDecision.ALLOW, "Command is allowlisted"

    deny_reason = is_denylisted(policy, command)
    if deny_reason:
        return PolicyDecision.DENY, deny_reason

    return PolicyDecision.ABSTAIN, "Command not in allowlist or denylist"
