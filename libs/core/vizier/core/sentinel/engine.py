"""SentinelEngine: three-tier pipeline (allowlist -> denylist -> secrets -> git -> Haiku)."""

from __future__ import annotations

from vizier.core.sentinel.allowlist import AllowlistPolicy
from vizier.core.sentinel.denylist import DenylistPolicy
from vizier.core.sentinel.git_classifier import GitOperationClassifier
from vizier.core.sentinel.haiku_evaluator import HaikuEvaluator, LLMCallable
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest
from vizier.core.sentinel.secret_scanner import SecretScanner


class SentinelEngine:
    """Three-tier security enforcement pipeline.

    Pipeline order (short-circuits on first decisive result):
    1. Allowlist (zero cost) -- instant ALLOW for known-safe calls
    2. Denylist (zero cost) -- instant DENY for known-dangerous calls
    3. Secret scanner (zero cost) -- DENY if secrets detected
    4. Git classifier (zero cost) -- ALLOW/DENY for git commands
    5. Haiku evaluator (LLM) -- for ambiguous calls (~$0.001/call)
    """

    def __init__(self, llm_callable: LLMCallable | None = None) -> None:
        self._allowlist = AllowlistPolicy()
        self._denylist = DenylistPolicy()
        self._secret_scanner = SecretScanner()
        self._git_classifier = GitOperationClassifier()
        self._haiku: HaikuEvaluator | None = None
        if llm_callable is not None:
            self._haiku = HaikuEvaluator(llm_callable)

    def evaluate(self, request: ToolCallRequest) -> SentinelResult:
        """Evaluate a tool call through the full pipeline.

        :param request: The tool call to evaluate.
        :returns: Final security decision.
        """
        result = self._allowlist.evaluate(request)
        if result.decision != PolicyDecision.ABSTAIN:
            return result

        result = self._denylist.evaluate(request)
        if result.decision != PolicyDecision.ABSTAIN:
            return result

        result = self._secret_scanner.scan(request)
        if result.decision != PolicyDecision.ABSTAIN:
            return result

        result = self._git_classifier.evaluate(request)
        if result.decision != PolicyDecision.ABSTAIN:
            return result

        if self._haiku is not None:
            return self._haiku.evaluate(request)

        return SentinelResult(
            decision=PolicyDecision.DENY,
            reason="No Haiku evaluator configured; denying ambiguous call (fail-closed)",
            policy="engine",
        )
