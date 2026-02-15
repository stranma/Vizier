"""Tool registry: combines worker restrictions with Sentinel enforcement."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

if TYPE_CHECKING:
    from vizier.core.sentinel.engine import SentinelEngine


class ToolRegistry:
    """Manages tool access by combining worker restrictions with Sentinel.

    :param allowed_tools: List of tools the worker can use.
    :param tool_restrictions: Per-tool allowed/denied patterns.
    :param sentinel: SentinelEngine for security enforcement.
    """

    def __init__(
        self,
        allowed_tools: list[str],
        tool_restrictions: dict[str, dict[str, list[str]]] | None = None,
        sentinel: SentinelEngine | None = None,
    ) -> None:
        self._allowed = set(allowed_tools)
        self._restrictions = tool_restrictions or {}
        self._sentinel = sentinel

    def check(self, request: ToolCallRequest) -> SentinelResult:
        """Check whether a tool call is permitted.

        :param request: The tool call to check.
        :returns: ALLOW or DENY result.
        """
        if request.tool not in self._allowed:
            return SentinelResult(
                decision=PolicyDecision.DENY,
                reason=f"Tool not in worker's allowed list: {request.tool}",
                policy="tool_registry",
            )

        if request.tool in self._restrictions:
            restriction_result = self._check_restrictions(request)
            if restriction_result.decision == PolicyDecision.DENY:
                return restriction_result

        if self._sentinel is not None:
            return self._sentinel.evaluate(request)

        return SentinelResult(
            decision=PolicyDecision.ALLOW,
            reason="Tool allowed and no Sentinel configured",
            policy="tool_registry",
        )

    def _check_restrictions(self, request: ToolCallRequest) -> SentinelResult:
        restrictions = self._restrictions[request.tool]
        command = request.command or request.args.get("command", "")

        denied_patterns = restrictions.get("denied_patterns", [])
        for pattern in denied_patterns:
            if re.search(pattern, command):
                return SentinelResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Command matches denied pattern: {pattern}",
                    policy="tool_registry",
                )

        allowed_patterns = restrictions.get("allowed_patterns", [])
        if allowed_patterns:
            for pattern in allowed_patterns:
                if re.search(pattern, command):
                    return SentinelResult(
                        decision=PolicyDecision.ALLOW,
                        reason=f"Command matches allowed pattern: {pattern}",
                        policy="tool_registry",
                    )
            return SentinelResult(
                decision=PolicyDecision.DENY,
                reason="Command does not match any allowed pattern",
                policy="tool_registry",
            )

        return SentinelResult(decision=PolicyDecision.ALLOW, reason="No restriction matched", policy="tool_registry")
