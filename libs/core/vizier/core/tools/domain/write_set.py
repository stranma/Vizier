"""Write-set enforcement via glob patterns (D55)."""

from __future__ import annotations

import re


class WriteSetChecker:
    """Checks file paths against glob-pattern write-set boundaries.

    Plugin defines write-set as glob patterns (e.g. ``src/**/*.py``, ``tests/**``).
    The checker validates that a given path matches at least one allowed pattern.

    Supports ``*`` (any non-separator chars), ``**`` (any path segments including none),
    and ``?`` (any single non-separator char).

    :param patterns: Allowed write-set glob patterns.
    :param project_root: Project root directory for relative path resolution.
    """

    def __init__(self, patterns: list[str], project_root: str = "") -> None:
        self._patterns = patterns
        self._compiled = [_glob_to_regex(p) for p in patterns]
        self._project_root = project_root

    @property
    def patterns(self) -> list[str]:
        """Return the configured write-set patterns."""
        return list(self._patterns)

    def is_allowed(self, path: str) -> bool:
        """Check if a file path is within the write-set.

        :param path: File path to check (absolute or relative).
        :returns: True if the path matches at least one write-set pattern.
        """
        if not self._patterns:
            return True

        rel_path = self._to_relative(path)
        return any(regex.fullmatch(rel_path) for regex in self._compiled)

    def _to_relative(self, path: str) -> str:
        """Convert an absolute path to relative (forward slashes)."""
        normalized = path.replace("\\", "/")
        root = self._project_root.replace("\\", "/").rstrip("/")
        if root and normalized.startswith(root + "/"):
            normalized = normalized[len(root) + 1 :]
        return normalized


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern to a compiled regex.

    Handles ``**`` (matches zero or more path segments), ``*`` (matches
    anything except path separator), and ``?`` (single non-separator char).
    """
    i = 0
    regex_parts: list[str] = []
    n = len(pattern)

    while i < n:
        ch = pattern[i]
        if ch == "*" and i + 1 < n and pattern[i + 1] == "*":
            if i + 2 < n and pattern[i + 2] == "/":
                regex_parts.append("(.*/)?")
                i += 3
            else:
                regex_parts.append(".*")
                i += 2
        elif ch == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif ch == "?":
            regex_parts.append("[^/]")
            i += 1
        elif ch in ".()[]{}+^$|":
            regex_parts.append("\\" + ch)
            i += 1
        else:
            regex_parts.append(ch)
            i += 1

    return re.compile("".join(regex_parts))
