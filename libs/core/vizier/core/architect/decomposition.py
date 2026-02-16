"""Decomposition logic: parse LLM output into sub-spec definitions."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field


class SubSpecDefinition(BaseModel):
    """Parsed sub-spec from Architect's LLM response.

    :param title: Short title for the sub-spec (becomes part of the spec ID).
    :param description: Full markdown description including acceptance criteria.
    :param complexity: Estimated complexity (low/medium/high).
    :param priority: Execution priority (lower = higher priority).
    :param artifacts: List of files this sub-spec will create/modify.
    :param criteria_refs: List of @criteria/ references used.
    """

    title: str
    description: str
    complexity: str = "medium"
    priority: int = Field(default=1, ge=1)
    artifacts: list[str] = Field(default_factory=list)
    criteria_refs: list[str] = Field(default_factory=list)


def parse_decomposition(response_text: str) -> list[SubSpecDefinition]:
    """Parse Architect LLM response into sub-spec definitions.

    Expects the response to contain sub-specs delimited by `## Sub-spec:` headers.
    Each sub-spec section can contain:
    - Title (from the header)
    - Description (body text)
    - Complexity: low|medium|high
    - Priority: integer
    - Artifacts: comma-separated file paths
    - @criteria/ references in the description

    :param response_text: Raw LLM response text.
    :returns: List of parsed SubSpecDefinition objects.
    """
    specs: list[SubSpecDefinition] = []

    sections = re.split(r"(?m)^## Sub-spec:\s*", response_text)

    for section in sections[1:]:
        lines = section.strip().split("\n")
        if not lines:
            continue

        title = lines[0].strip()
        if not title:
            continue

        body_lines: list[str] = []
        complexity = "medium"
        priority = len(specs) + 1
        artifacts: list[str] = []

        for line in lines[1:]:
            stripped = line.strip()

            complexity_match = re.match(r"(?i)^complexity:\s*(low|medium|high)$", stripped)
            if complexity_match:
                complexity = complexity_match.group(1).lower()
                continue

            priority_match = re.match(r"(?i)^priority:\s*(\d+)$", stripped)
            if priority_match:
                priority = int(priority_match.group(1))
                continue

            artifacts_match = re.match(r"(?i)^artifacts:\s*(.+)$", stripped)
            if artifacts_match:
                artifacts = [a.strip() for a in artifacts_match.group(1).split(",") if a.strip()]
                continue

            body_lines.append(line)

        description = "\n".join(body_lines).strip()
        criteria_refs = re.findall(r"@criteria/(\w+)", description)

        specs.append(
            SubSpecDefinition(
                title=title,
                description=description,
                complexity=complexity,
                priority=priority,
                artifacts=artifacts,
                criteria_refs=criteria_refs,
            )
        )

    return specs


def estimate_complexity(description: str, criteria_count: int = 0, artifact_count: int = 0) -> str:
    """Estimate spec complexity from heuristics.

    :param description: The spec description text.
    :param criteria_count: Number of acceptance criteria.
    :param artifact_count: Number of artifacts to produce.
    :returns: Complexity string: "low", "medium", or "high".
    """
    score = 0

    word_count = len(description.split())
    if word_count > 200:
        score += 2
    elif word_count > 100:
        score += 1

    score += min(criteria_count, 3)
    score += min(artifact_count, 3)

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def generate_sub_spec_id(parent_id: str, index: int, title: str) -> str:
    """Generate a sub-spec ID from parent ID and title.

    :param parent_id: Parent spec ID (e.g. "001-add-auth").
    :param index: Sub-spec index (1-based).
    :param title: Sub-spec title.
    :returns: Sub-spec ID (e.g. "001-add-auth-01-data-model").
    """
    slug = title.lower().replace(" ", "-")[:30]
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "subtask"
    return f"{parent_id}-{index:02d}-{slug}"
