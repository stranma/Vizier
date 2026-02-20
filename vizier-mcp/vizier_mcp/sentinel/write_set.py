"""WriteSetChecker -- glob pattern enforcement for file writes.

Converts glob patterns (supporting **, *, ?) to regex and validates
file paths against the project's write-set from sentinel.yaml.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern to a compiled regex.

    Supports:
    - ** : matches zero or more path segments (including separators)
    - *  : matches any characters except path separator
    - ?  : matches a single character except path separator

    :param pattern: Glob pattern string.
    :return: Compiled regex pattern.
    """
    i = 0
    n = len(pattern)
    result: list[str] = []
    result.append("^")

    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                if i + 2 < n and pattern[i + 2] == "/":
                    result.append("(?:.*/)?")
                    i += 3
                else:
                    result.append(".*")
                    i += 2
            else:
                result.append("[^/]*")
                i += 1
        elif c == "?":
            result.append("[^/]")
            i += 1
        elif c in r".+^${}()|[]\\":
            result.append("\\" + c)
            i += 1
        else:
            result.append(c)
            i += 1

    result.append("$")
    return re.compile("".join(result))


class WriteSetChecker:
    """Validates file paths against a set of glob patterns.

    Empty patterns list means all writes are allowed.
    Paths containing '..' components are always rejected (traversal prevention).

    :param patterns: List of glob pattern strings from sentinel.yaml write_set.
    """

    def __init__(self, patterns: list[str]) -> None:
        self._patterns = patterns
        self._compiled = [_glob_to_regex(p) for p in patterns]

    def is_allowed(self, file_path: str) -> bool:
        """Check if a file path matches any write-set pattern.

        Rejects absolute paths and paths with '..' components to prevent traversal.

        :param file_path: Relative file path to check.
        :return: True if the path matches a pattern (or patterns list is empty).
        """
        if not self._compiled:
            return True

        path = PurePosixPath(file_path)
        if path.is_absolute():
            return False
        if ".." in path.parts:
            return False

        normalized = str(path)
        return any(regex.match(normalized) for regex in self._compiled)
