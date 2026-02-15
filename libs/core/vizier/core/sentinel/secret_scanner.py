"""Secret scanner: regex-based detection of credentials in tool call arguments."""

from __future__ import annotations

import re

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("AWS Secret Key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+")),
    ("API Key Assignment", re.compile(r"(?i)(ANTHROPIC_API_KEY|OPENAI_API_KEY|[A-Z_]*_API_KEY)\s*[=:]\s*\S+")),
    ("Bearer Token", re.compile(r"(?i)(bearer|auth[_-]?token|access[_-]?token)\s*[=:]\s*\S+")),
    ("Password Assignment", re.compile(r"(?i)(password|passwd|pwd)\s*[=:]\s*\S+")),
    ("Private Key Block", re.compile(r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("Generic Secret", re.compile(r"(?i)(secret|private[_-]?key)\s*[=:]\s*['\"]?[A-Za-z0-9+/=]{20,}")),
]


class SecretScanner:
    """Scans tool call arguments for embedded secrets."""

    def scan(self, request: ToolCallRequest) -> SentinelResult:
        """Scan a tool call for secrets in its arguments.

        :param request: The tool call to scan.
        :returns: DENY if a secret is detected, ABSTAIN otherwise.
        """
        text_to_scan = self._extract_text(request)
        if not text_to_scan:
            return SentinelResult(
                decision=PolicyDecision.ABSTAIN, reason="No scannable content", policy="secret_scanner"
            )

        for name, pattern in SECRET_PATTERNS:
            if pattern.search(text_to_scan):
                return SentinelResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Secret detected: {name}",
                    policy="secret_scanner",
                )

        return SentinelResult(decision=PolicyDecision.ABSTAIN, reason="No secrets found", policy="secret_scanner")

    @staticmethod
    def _extract_text(request: ToolCallRequest) -> str:
        parts: list[str] = [request.command]
        for value in request.args.values():
            if isinstance(value, str):
                parts.append(value)
        return "\n".join(parts)
