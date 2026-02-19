"""Evidence completeness checker (D56).

Validates that all plugin-mandatory evidence types exist before
accepting a QUALITY_VERDICT for the DONE transition.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class EvidenceCheckResult:
    """Result of an evidence completeness check."""

    complete: bool
    missing: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)


EVIDENCE_TYPES_SOFTWARE = ["test_output", "lint_output", "type_check_output", "diff"]
EVIDENCE_TYPES_DOCUMENTS = ["link_check_output", "structure_validation", "rendered_preview_path"]


class EvidenceChecker:
    """Validates that all required evidence types are present.

    :param required_types: List of required evidence type names.
    :param evidence_dir: Directory where evidence files are stored.
    """

    def __init__(self, required_types: list[str], evidence_dir: str) -> None:
        self._required = required_types
        self._evidence_dir = evidence_dir

    @property
    def required_types(self) -> list[str]:
        """Return the required evidence types."""
        return list(self._required)

    def check(self) -> EvidenceCheckResult:
        """Check if all required evidence files exist.

        Looks for files matching the evidence type name (with any extension)
        in the evidence directory.

        :returns: EvidenceCheckResult with complete flag and missing/found lists.
        """
        found: list[str] = []
        missing: list[str] = []

        for ev_type in self._required:
            if self._find_evidence_file(ev_type):
                found.append(ev_type)
            else:
                missing.append(ev_type)

        return EvidenceCheckResult(
            complete=len(missing) == 0,
            missing=missing,
            found=found,
        )

    def _find_evidence_file(self, evidence_type: str) -> bool:
        """Check if an evidence file exists for the given type.

        Matches files whose name (without extension) equals the evidence type,
        or files whose name starts with the evidence type.
        """
        if not os.path.isdir(self._evidence_dir):
            return False
        for filename in os.listdir(self._evidence_dir):
            name_no_ext = os.path.splitext(filename)[0]
            if name_no_ext == evidence_type:
                return True
        return False


def get_required_evidence(plugin_name: str) -> list[str]:
    """Return the required evidence types for a plugin.

    :param plugin_name: Plugin identifier (e.g. 'software', 'documents').
    :returns: List of required evidence type names.
    """
    registry: dict[str, list[str]] = {
        "software": EVIDENCE_TYPES_SOFTWARE,
        "documents": EVIDENCE_TYPES_DOCUMENTS,
    }
    return registry.get(plugin_name, [])
