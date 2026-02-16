"""Allowlist policy: auto-approve known-safe tool calls (zero cost)."""

from __future__ import annotations

import re

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

SAFE_TOOLS: set[str] = {
    "read_file",
    "file_read",
    "glob",
    "grep",
    "ls",
}

SAFE_COMMAND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^git\s+(status|log|diff|branch|show|rev-parse)\b"),
    re.compile(r"^git\s+(blame|reflog|describe|shortlog|rev-list)\b"),
    re.compile(r"^git\s+stash\b"),
    re.compile(r"^git\s+fetch\b"),
    re.compile(r"^git\s+pull\b"),
    re.compile(r"^git\s+add\b"),
    re.compile(r"^git\s+remote\b"),
    re.compile(r"^git\s+tag\b"),
    re.compile(r"^git\s+commit\b"),
    re.compile(r"^git\s+push\b(?!.*(-f\b|--force))"),
    re.compile(r"^git\s+checkout\s+-b\s+"),
    re.compile(r"^(uv\s+run\s+)?pytest\b"),
    re.compile(r"^(uv\s+run\s+)?ruff\s+(check|format)\b"),
    re.compile(r"^(uv\s+run\s+)?pyright\b"),
    re.compile(r"^(uv\s+run\s+)?npm\s+test\b"),
    re.compile(r"^echo\b"),
    re.compile(r"^cat\b"),
    re.compile(r"^ls\b"),
    re.compile(r"^mkdir\b"),
    re.compile(r"^head\b"),
    re.compile(r"^tail\b"),
]


class AllowlistPolicy:
    """Deterministic zero-cost allowlist for known-safe tool calls."""

    def evaluate(self, request: ToolCallRequest) -> SentinelResult:
        """Evaluate a tool call against the allowlist.

        :param request: The tool call to evaluate.
        :returns: ALLOW if matched, ABSTAIN otherwise.
        """
        if request.tool in SAFE_TOOLS:
            return SentinelResult(
                decision=PolicyDecision.ALLOW, reason=f"Safe tool: {request.tool}", policy="allowlist"
            )

        if request.tool in ("bash", "shell", "terminal"):
            command = request.command or request.args.get("command", "")
            for pattern in SAFE_COMMAND_PATTERNS:
                if pattern.search(command):
                    return SentinelResult(
                        decision=PolicyDecision.ALLOW,
                        reason=f"Safe command pattern: {command[:80]}",
                        policy="allowlist",
                    )

        if request.tool in ("file_write", "write_file", "file_edit"):
            return SentinelResult(
                decision=PolicyDecision.ALLOW, reason=f"File write tool: {request.tool}", policy="allowlist"
            )

        return SentinelResult(decision=PolicyDecision.ABSTAIN, reason="Not in allowlist", policy="allowlist")
