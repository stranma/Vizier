"""Sentinel policy engine (allowlist/denylist/Haiku).

Provides the three-tier security enforcement for the Vizier MCP server:
- Write-set validation via glob patterns
- Command checking via allowlist -> denylist -> Haiku
- Web fetch scanning for prompt injection
"""

from vizier_mcp.sentinel.haiku import LLMCallable, evaluate_command
from vizier_mcp.sentinel.policy import (
    check_role_permission,
    is_allowlisted,
    is_denylisted,
    load_policy,
)
from vizier_mcp.sentinel.policy import (
    evaluate_command as evaluate_command_policy,
)
from vizier_mcp.sentinel.write_set import WriteSetChecker

__all__ = [
    "LLMCallable",
    "WriteSetChecker",
    "check_role_permission",
    "evaluate_command",
    "evaluate_command_policy",
    "is_allowlisted",
    "is_denylisted",
    "load_policy",
]
