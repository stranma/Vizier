"""Criteria library loader: reads criteria definitions from plugin directories."""

from __future__ import annotations

from pathlib import Path


class CriteriaLibraryLoader:
    """Loads criteria definitions from a plugin's criteria/ directory.

    :param criteria_dir: Path to the criteria/ directory.
    """

    def __init__(self, criteria_dir: str | Path) -> None:
        self._dir = Path(criteria_dir)

    def load(self) -> dict[str, str]:
        """Load all criteria files into a name -> definition mapping.

        :returns: Dict of criteria_name -> definition text.
        """
        if not self._dir.exists():
            return {}

        library: dict[str, str] = {}
        for path in sorted(self._dir.glob("*.md")):
            name = path.stem
            library[name] = path.read_text(encoding="utf-8").strip()
        return library

    def get(self, name: str) -> str | None:
        """Load a single criterion by name.

        :param name: Criterion name (without .md extension).
        :returns: Definition text, or None if not found.
        """
        path = self._dir / f"{name}.md"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8").strip()
