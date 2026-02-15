"""Criteria reference resolution and snapshotting."""

from __future__ import annotations

import re

CRITERIA_PATTERN = re.compile(r"@criteria/(\w+)")


def resolve_criteria_references(content: str) -> list[str]:
    """Find all @criteria/ references in spec content.

    :param content: Markdown content of a spec.
    :returns: List of criteria names referenced (e.g. ["tests_pass", "lint_clean"]).
    """
    return CRITERIA_PATTERN.findall(content)


def snapshot_criteria(content: str, criteria_library: dict[str, str]) -> str:
    """Resolve and inline @criteria/ references using the provided library.

    Each @criteria/NAME reference is expanded with the full definition text
    from the library appended after the reference line.

    :param content: Markdown content of a spec.
    :param criteria_library: Mapping of criteria_name -> full definition text.
    :returns: Updated content with criteria definitions inlined.
    """
    refs = resolve_criteria_references(content)
    if not refs:
        return content

    result = content
    for ref_name in refs:
        definition = criteria_library.get(ref_name)
        if definition is None:
            continue
        pattern = f"@criteria/{ref_name}"
        snapshot_block = (
            f"@criteria/{ref_name}\n  <!-- snapshot: {ref_name} -->\n  {definition.strip()}\n  <!-- /snapshot -->"
        )
        result = result.replace(pattern, snapshot_block, 1)

    return result
