"""Deterministic message classifier for EA JIT prompt assembly.

Uses regex + keyword + slash command detection to classify incoming messages
and determine which prompt modules to load. Zero LLM cost for routing.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel


class MessageCategory(StrEnum):
    """Message intent categories for EA routing."""

    DELEGATION = "delegation"
    STATUS = "status"
    CONTROL = "control"
    SESSION = "session"
    BRIEFING = "briefing"
    CHECKIN = "checkin"
    QUICK_QUERY = "quick_query"
    FOCUS = "focus"
    APPROVAL = "approval"
    BUDGET = "budget"
    PRIORITIES = "priorities"
    FILE_OPS = "file_ops"
    CROSS_PROJECT = "cross_project"
    DIRECT_QA = "direct_qa"
    GENERAL = "general"


class PromptModule(StrEnum):
    """JIT prompt modules that can be loaded based on message classification."""

    CORE = "core"
    CHECKIN = "checkin"
    FILE_OPS = "file_ops"
    CALENDAR = "calendar"
    CROSS_PROJECT = "cross_project"
    BUDGET = "budget"
    BRIEFING = "briefing"
    PROACTIVE = "proactive"
    SESSION = "session"
    APPROVAL = "approval"


class ClassificationResult(BaseModel):
    """Result of message classification."""

    category: MessageCategory
    modules: list[PromptModule]
    project: str = ""
    extra: dict[str, str] = {}


SLASH_COMMANDS: dict[str, MessageCategory] = {
    "/status": MessageCategory.STATUS,
    "/ask": MessageCategory.QUICK_QUERY,
    "/checkin": MessageCategory.CHECKIN,
    "/focus": MessageCategory.FOCUS,
    "/session": MessageCategory.SESSION,
    "/approve": MessageCategory.APPROVAL,
    "/budget": MessageCategory.BUDGET,
    "/priorities": MessageCategory.PRIORITIES,
}

CATEGORY_MODULES: dict[MessageCategory, list[PromptModule]] = {
    MessageCategory.DELEGATION: [PromptModule.CORE],
    MessageCategory.STATUS: [PromptModule.CORE],
    MessageCategory.CONTROL: [PromptModule.CORE],
    MessageCategory.SESSION: [PromptModule.CORE, PromptModule.SESSION],
    MessageCategory.BRIEFING: [PromptModule.CORE, PromptModule.BRIEFING],
    MessageCategory.CHECKIN: [PromptModule.CORE, PromptModule.CHECKIN],
    MessageCategory.QUICK_QUERY: [PromptModule.CORE],
    MessageCategory.FOCUS: [PromptModule.CORE],
    MessageCategory.APPROVAL: [PromptModule.CORE, PromptModule.APPROVAL],
    MessageCategory.BUDGET: [PromptModule.CORE, PromptModule.BUDGET],
    MessageCategory.PRIORITIES: [PromptModule.CORE],
    MessageCategory.FILE_OPS: [PromptModule.CORE, PromptModule.FILE_OPS],
    MessageCategory.CROSS_PROJECT: [PromptModule.CORE, PromptModule.CROSS_PROJECT],
    MessageCategory.DIRECT_QA: [PromptModule.CORE],
    MessageCategory.GENERAL: [PromptModule.CORE],
}

_DELEGATION_PATTERNS = [
    re.compile(r"\b(build|create|implement|add|make|write|develop|design|fix|update|deploy)\b", re.IGNORECASE),
]
_STATUS_PATTERNS = [
    re.compile(
        r"\b(status|how('?s| is) (it|everything|the project)|progress|what('?s| is) happening)\b", re.IGNORECASE
    ),
]
_CONTROL_PATTERNS = [
    re.compile(r"\b(stop|cancel|pause|resume|abort|halt)\s+(work|task|spec)\b", re.IGNORECASE),
]
_FILE_PATTERNS = [
    re.compile(r"\b(file|document|checkout|check.?out|check.?in|download|upload|send me|edit the)\b", re.IGNORECASE),
]
_CALENDAR_PATTERNS = [
    re.compile(r"\b(meeting|calendar|schedule|appointment|call with)\b", re.IGNORECASE),
]
_CROSS_PROJECT_PATTERNS = [
    re.compile(r"\b(all projects|across projects|every project|cross.?project|multiple projects)\b", re.IGNORECASE),
]
_QA_PATTERNS = [
    re.compile(
        r"\b(what (framework|language|version|library)|how (does|do)|where (is|are)|which (file|module))\b",
        re.IGNORECASE,
    ),
]

_PROJECT_PATTERN = re.compile(r"(?:project[- ]?|for\s+)([a-zA-Z0-9_-]+)", re.IGNORECASE)
_FOCUS_DURATION_PATTERN = re.compile(r"(\d+)\s*h", re.IGNORECASE)


class MessageClassifier:
    """Deterministic message classifier using regex and keyword detection.

    Zero LLM cost -- all classification is done via pattern matching.
    """

    def classify(self, message: str) -> ClassificationResult:
        """Classify an incoming message to determine category and required modules.

        :param message: The incoming message text.
        :returns: Classification result with category, modules, and extracted data.
        """
        message = message.strip()

        slash_result = self._check_slash_commands(message)
        if slash_result is not None:
            return slash_result

        category = self._classify_by_patterns(message)
        modules = list(CATEGORY_MODULES.get(category, [PromptModule.CORE]))

        if any(p.search(message) for p in _CALENDAR_PATTERNS) and PromptModule.CALENDAR not in modules:
            modules.append(PromptModule.CALENDAR)

        if any(p.search(message) for p in _CROSS_PROJECT_PATTERNS):
            category = MessageCategory.CROSS_PROJECT
            modules = list(CATEGORY_MODULES[MessageCategory.CROSS_PROJECT])

        project = self._extract_project(message)
        return ClassificationResult(category=category, modules=modules, project=project)

    def _check_slash_commands(self, message: str) -> ClassificationResult | None:
        """Check if message starts with a known slash command."""
        for cmd, category in SLASH_COMMANDS.items():
            if message.lower().startswith(cmd):
                modules = list(CATEGORY_MODULES.get(category, [PromptModule.CORE]))
                project = ""
                extra: dict[str, str] = {}

                remainder = message[len(cmd) :].strip()
                if category == MessageCategory.QUICK_QUERY and remainder:
                    parts = remainder.split(maxsplit=1)
                    project = parts[0]
                    if len(parts) > 1:
                        extra["query"] = parts[1]
                elif category == MessageCategory.FOCUS and remainder:
                    match = _FOCUS_DURATION_PATTERN.search(remainder)
                    if match:
                        extra["duration_hours"] = match.group(1)
                elif category == MessageCategory.APPROVAL and remainder:
                    extra["spec_id"] = remainder.split()[0]
                elif (
                    category in (MessageCategory.STATUS, MessageCategory.BUDGET, MessageCategory.SESSION) and remainder
                ):
                    project = remainder.split()[0]

                if not project:
                    project = self._extract_project(message)

                return ClassificationResult(category=category, modules=modules, project=project, extra=extra)
        return None

    def _classify_by_patterns(self, message: str) -> MessageCategory:
        """Classify by regex patterns, returning the best match."""
        if any(p.search(message) for p in _CONTROL_PATTERNS):
            return MessageCategory.CONTROL

        if any(p.search(message) for p in _FILE_PATTERNS):
            return MessageCategory.FILE_OPS

        if any(p.search(message) for p in _STATUS_PATTERNS):
            return MessageCategory.STATUS

        if any(p.search(message) for p in _QA_PATTERNS):
            return MessageCategory.DIRECT_QA

        if any(p.search(message) for p in _DELEGATION_PATTERNS):
            return MessageCategory.DELEGATION

        return MessageCategory.GENERAL

    def _extract_project(self, message: str) -> str:
        """Extract project name from message if present."""
        match = _PROJECT_PATTERN.search(message)
        return match.group(1) if match else ""
