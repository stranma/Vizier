"""Denylist policy: auto-block known-dangerous tool calls (zero cost)."""

from __future__ import annotations

import re

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

DANGEROUS_COMMAND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\s+-rf\b"),
    re.compile(r"\brm\s+-r\s+/\b"),
    re.compile(r"\bgit\s+push\s+.*--force\b"),
    re.compile(r"\bgit\s+push\s+-f"),
    re.compile(r"\bgit\s+reset\s+--hard\b"),
    re.compile(r"\bgit\s+rebase\s+-i\b"),
    re.compile(r"\bgit\s+clean\s+-f"),
    re.compile(r"\bgit\s+branch\s+-D\b"),
    re.compile(r"\bchmod\s+777\b"),
    re.compile(r"\bcurl\s+.*\|\s*(ba)?sh\b"),
    re.compile(r"\bwget\s+.*\|\s*(ba)?sh\b"),
    re.compile(r"\b(sudo\s+)?dd\s+.*of=/dev/"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bformat\s+[A-Z]:\b", re.IGNORECASE),
]

DANGEROUS_TOOLS: set[str] = {
    "run_sql_delete",
    "drop_table",
    "delete_database",
}


class DenylistPolicy:
    """Deterministic zero-cost denylist for known-dangerous tool calls."""

    def evaluate(self, request: ToolCallRequest) -> SentinelResult:
        """Evaluate a tool call against the denylist.

        :param request: The tool call to evaluate.
        :returns: DENY if matched, ABSTAIN otherwise.
        """
        if request.tool in DANGEROUS_TOOLS:
            return SentinelResult(
                decision=PolicyDecision.DENY, reason=f"Dangerous tool: {request.tool}", policy="denylist"
            )

        if request.tool in ("bash", "shell", "terminal"):
            command = request.command or request.args.get("command", "")
            for pattern in DANGEROUS_COMMAND_PATTERNS:
                if pattern.search(command):
                    return SentinelResult(
                        decision=PolicyDecision.DENY,
                        reason=f"Dangerous command pattern: {command[:80]}",
                        policy="denylist",
                    )

        return SentinelResult(decision=PolicyDecision.ABSTAIN, reason="Not in denylist", policy="denylist")
