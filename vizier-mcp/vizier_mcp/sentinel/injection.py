"""Prompt injection pattern scanner for web fetch content.

Regex-based scanning for common prompt injection patterns.
Used by web_fetch_checked to detect potentially unsafe content.
"""

from __future__ import annotations

import re

INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE), "Prompt injection: ignore previous instructions"),
    (re.compile(r"ignore\s+all\s+previous", re.IGNORECASE), "Prompt injection: ignore all previous"),
    (re.compile(r"you\s+are\s+now\s+", re.IGNORECASE), "Prompt injection: role reassignment"),
    (re.compile(r"disregard\s+your\s+system\s+prompt", re.IGNORECASE), "Prompt injection: disregard system prompt"),
    (re.compile(r"^SYSTEM:", re.MULTILINE), "Prompt injection: fake SYSTEM block"),
    (re.compile(r"^assistant:", re.MULTILINE | re.IGNORECASE), "Prompt injection: fake assistant block"),
    (re.compile(r"forget\s+(everything|all)\s+(you|your)", re.IGNORECASE), "Prompt injection: memory wipe attempt"),
    (re.compile(r"new\s+instructions?\s*:", re.IGNORECASE), "Prompt injection: instruction override"),
]


def scan_for_injection(content: str) -> str | None:
    """Scan content for prompt injection patterns.

    :param content: The text content to scan.
    :return: Reason string if injection detected, None if clean.
    """
    for pattern, reason in INJECTION_PATTERNS:
        if pattern.search(content):
            return reason
    return None
