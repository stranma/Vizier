"""Git operation classifier: categorizes git commands as safe/dangerous/needs_approval."""

from __future__ import annotations

import re
from enum import StrEnum

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest


class GitSafety(StrEnum):
    SAFE = "safe"
    DANGEROUS = "dangerous"
    NEEDS_APPROVAL = "needs_approval"


SAFE_GIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^git\s+(status|log|diff|show|branch|tag|remote|stash\s+list|rev-parse|ls-files)\b"),
    re.compile(r"^git\s+commit\b"),
    re.compile(r"^git\s+add\b"),
    re.compile(r"^git\s+push\b(?!.*(-f|--force))"),
    re.compile(r"^git\s+pull\b"),
    re.compile(r"^git\s+fetch\b"),
    re.compile(r"^git\s+checkout\s+-b\b"),
    re.compile(r"^git\s+switch\b"),
    re.compile(r"^git\s+merge\b(?!.*--abort)"),
    re.compile(r"^git\s+clone\b"),
]

DANGEROUS_GIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^git\s+push\s+.*(-f|--force)\b"),
    re.compile(r"^git\s+reset\s+--hard\b"),
    re.compile(r"^git\s+rebase\s+-i\b"),
    re.compile(r"^git\s+clean\s+-f"),
    re.compile(r"^git\s+branch\s+-D\b"),
    re.compile(r"^git\s+checkout\s+\.\s*$"),
    re.compile(r"^git\s+restore\s+\.\s*$"),
]


class GitOperationClassifier:
    """Classifies git commands by safety level."""

    def classify(self, command: str) -> GitSafety:
        """Classify a git command.

        :param command: The git command string.
        :returns: Safety classification.
        """
        command = command.strip()
        if not command.startswith("git"):
            return GitSafety.SAFE

        for pattern in DANGEROUS_GIT_PATTERNS:
            if pattern.search(command):
                return GitSafety.DANGEROUS

        for pattern in SAFE_GIT_PATTERNS:
            if pattern.search(command):
                return GitSafety.SAFE

        return GitSafety.NEEDS_APPROVAL

    def evaluate(self, request: ToolCallRequest) -> SentinelResult:
        """Evaluate a tool call if it's a git command.

        :param request: The tool call to evaluate.
        :returns: DENY for dangerous, ALLOW for safe, ABSTAIN otherwise.
        """
        if request.tool not in ("bash", "shell", "terminal"):
            return SentinelResult(
                decision=PolicyDecision.ABSTAIN, reason="Not a shell command", policy="git_classifier"
            )

        command = request.command or request.args.get("command", "")
        if not command.strip().startswith("git"):
            return SentinelResult(decision=PolicyDecision.ABSTAIN, reason="Not a git command", policy="git_classifier")

        safety = self.classify(command)
        if safety == GitSafety.DANGEROUS:
            return SentinelResult(
                decision=PolicyDecision.DENY,
                reason=f"Dangerous git operation: {command[:80]}",
                policy="git_classifier",
            )
        if safety == GitSafety.SAFE:
            return SentinelResult(
                decision=PolicyDecision.ALLOW,
                reason=f"Safe git operation: {command[:80]}",
                policy="git_classifier",
            )
        return SentinelResult(
            decision=PolicyDecision.ABSTAIN, reason="Git command needs review", policy="git_classifier"
        )
