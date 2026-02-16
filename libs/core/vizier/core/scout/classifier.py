"""Scout classifier: deterministic triage of specs into RESEARCH or SKIP."""

from __future__ import annotations

import re
from enum import StrEnum

from vizier.core.models.spec import Spec  # noqa: TC001


class ScoutDecision(StrEnum):
    """Scout triage outcome."""

    RESEARCH = "RESEARCH"
    SKIP = "SKIP"


_RESEARCH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(add|implement|integrate|new|feature|build|create|support|connect|expose)\b", re.IGNORECASE),
]

_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(fix|refactor|rename|update|remove|delete|bugfix|typo|cleanup|deprecate)\b", re.IGNORECASE),
]


class ScoutClassifier:
    """Deterministic keyword-based classifier for scout triage.

    Matches spec title and content against known patterns to decide
    whether external research is worthwhile.
    """

    def classify(self, spec: Spec) -> ScoutDecision:
        """Classify a spec as needing research or not.

        :param spec: The spec to classify.
        :returns: RESEARCH or SKIP decision.
        """
        text = f"{spec.frontmatter.id} {spec.content}"

        skip_score = sum(1 for p in _SKIP_PATTERNS if p.search(text))
        research_score = sum(1 for p in _RESEARCH_PATTERNS if p.search(text))

        if skip_score > 0 and research_score == 0:
            return ScoutDecision.SKIP

        return ScoutDecision.RESEARCH
