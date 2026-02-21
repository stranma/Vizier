"""Pydantic models for the Sentinel security subsystem.

Covers policy configuration (loaded from sentinel.yaml), write-set patterns,
command/web-fetch result shapes (D78), and the Haiku evaluator verdict.
"""

from __future__ import annotations

import enum

from pydantic import BaseModel, Field


class PolicyDecision(enum.StrEnum):
    """Result of a Sentinel policy evaluation."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ABSTAIN = "ABSTAIN"


class DenylistEntry(BaseModel):
    """A denylist entry -- either a simple pattern string or pattern+reason."""

    pattern: str
    reason: str = "Denied by policy"


class RolePermissions(BaseModel):
    """Per-role permission flags from sentinel.yaml."""

    can_write: bool = True
    can_bash: bool = True
    can_read: bool = True


class SecretScope(BaseModel):
    """A named scope mapping command patterns to secret environment variables.

    :param commands: fnmatch patterns for matching commands (e.g. ``["git *"]``).
    :param secrets: Environment variable names to inject (e.g. ``["GITHUB_TOKEN"]``).
    """

    commands: list[str]
    secrets: list[str]


class SentinelPolicy(BaseModel):
    """Project-level Sentinel policy loaded from sentinel.yaml.

    :param write_set: Glob patterns for allowed file write paths.
    :param command_allowlist: Commands/patterns that are always allowed.
    :param command_denylist: Commands/patterns that are always blocked.
    :param role_permissions: Per-role permission flags.
    :param secret_scopes: Named scopes mapping command patterns to secrets (D81).
    """

    write_set: list[str] = Field(default_factory=list)
    command_allowlist: list[str] = Field(default_factory=list)
    command_denylist: list[str | DenylistEntry] = Field(default_factory=list)
    role_permissions: dict[str, RolePermissions] = Field(default_factory=dict)
    secret_scopes: dict[str, SecretScope] = Field(default_factory=dict)


class CommandCheckResult(BaseModel):
    """Result of run_command_checked (D78 three-shape contract).

    Shape 1 - Denied: allowed=False, reason set
    Shape 2 - Succeeded: allowed=True, exit_code=0, stdout/stderr set
    Shape 3 - Failed: allowed=True, exit_code!=0, stdout/stderr set
    """

    allowed: bool
    reason: str | None = None
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None


class WebFetchResult(BaseModel):
    """Result of web_fetch_checked (D78 three-shape contract).

    Shape 1 - Blocked: safe=False, reason set
    Shape 2 - Fetched: safe=True, content set, status_code=200
    Shape 3 - Failed: safe=True, content="", status_code=N, error set
    """

    safe: bool
    reason: str | None = None
    content: str | None = None
    status_code: int | None = None
    error: str | None = None


class HaikuVerdict(BaseModel):
    """Verdict from the Haiku evaluator for ambiguous commands."""

    decision: PolicyDecision
    reason: str
    cost_usd: float = 0.0
