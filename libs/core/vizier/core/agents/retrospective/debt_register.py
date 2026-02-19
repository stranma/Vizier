"""Process debt register: tracks recurring patterns across specs.

Identifies and records recurring problems like repeated rejections,
stuck patterns, budget overruns, and frequent tool failures.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class DebtEntry:
    """A single process debt entry.

    :param pattern: Description of the recurring pattern.
    :param severity: LOW, MEDIUM, or HIGH.
    :param frequency: Number of occurrences.
    :param first_seen: ISO timestamp of first occurrence.
    :param evidence: List of spec IDs or trace references.
    :param resolution: Proposed resolution (empty if unresolved).
    """

    pattern: str
    severity: str = "MEDIUM"
    frequency: int = 1
    first_seen: str = ""
    evidence: list[str] = field(default_factory=list)
    resolution: str = ""

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "pattern": self.pattern,
            "severity": self.severity,
            "frequency": self.frequency,
            "first_seen": self.first_seen,
            "evidence": self.evidence,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DebtEntry:
        """Deserialize from dictionary."""
        return cls(
            pattern=data.get("pattern", ""),
            severity=data.get("severity", "MEDIUM"),
            frequency=data.get("frequency", 1),
            first_seen=data.get("first_seen", ""),
            evidence=data.get("evidence", []),
            resolution=data.get("resolution", ""),
        )


class DebtRegister:
    """Manages the process debt register.

    :param register_path: Path to the debt register JSON file.
    """

    def __init__(self, register_path: str) -> None:
        self._path = register_path
        self._entries: list[DebtEntry] = []
        self._load()

    @property
    def entries(self) -> list[DebtEntry]:
        """Current debt entries."""
        return list(self._entries)

    def add(self, pattern: str, severity: str = "MEDIUM", evidence: str = "") -> DebtEntry:
        """Add or update a debt entry.

        If a matching pattern exists, increment its frequency and add evidence.
        Otherwise create a new entry.

        :param pattern: Pattern description.
        :param severity: LOW, MEDIUM, or HIGH.
        :param evidence: Spec ID or trace reference.
        :returns: The created or updated entry.
        """
        for entry in self._entries:
            if entry.pattern == pattern:
                entry.frequency += 1
                if evidence and evidence not in entry.evidence:
                    entry.evidence.append(evidence)
                if severity == "HIGH" and entry.severity != "HIGH":
                    entry.severity = severity
                self._save()
                return entry

        entry = DebtEntry(
            pattern=pattern,
            severity=severity,
            frequency=1,
            first_seen=datetime.now(UTC).isoformat(),
            evidence=[evidence] if evidence else [],
        )
        self._entries.append(entry)
        self._save()
        return entry

    def resolve(self, pattern: str, resolution: str) -> bool:
        """Mark a debt entry as resolved.

        :param pattern: Pattern description to resolve.
        :param resolution: Resolution description.
        :returns: True if found and resolved.
        """
        for entry in self._entries:
            if entry.pattern == pattern:
                entry.resolution = resolution
                self._save()
                return True
        return False

    def unresolved(self) -> list[DebtEntry]:
        """Return all unresolved debt entries."""
        return [e for e in self._entries if not e.resolution]

    def high_severity(self) -> list[DebtEntry]:
        """Return all HIGH severity entries."""
        return [e for e in self._entries if e.severity == "HIGH"]

    def format_register(self) -> str:
        """Format the register as a human-readable summary.

        :returns: Formatted register text.
        """
        if not self._entries:
            return "No process debt recorded."

        lines: list[str] = []
        for entry in sorted(self._entries, key=lambda e: -e.frequency):
            status = f"[RESOLVED: {entry.resolution}]" if entry.resolution else "[OPEN]"
            lines.append(
                f"- {status} [{entry.severity}] {entry.pattern} "
                f"(freq: {entry.frequency}, evidence: {len(entry.evidence)})"
            )
        return "\n".join(lines)

    def _load(self) -> None:
        """Load register from disk."""
        if not os.path.isfile(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._entries = [DebtEntry.from_dict(d) for d in data]
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        """Save register to disk."""
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump([e.to_dict() for e in self._entries], f, indent=2)
