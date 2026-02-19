"""Search tools: glob, grep."""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any

from vizier.core.runtime.types import ToolDefinition


def create_glob_tool(project_root: str = "") -> ToolDefinition:
    """Create the glob tool for finding files by pattern.

    :param project_root: Project root for path resolution.
    :returns: ToolDefinition for glob.
    """

    def handler(*, pattern: str, path: str = "") -> dict[str, Any]:
        search_root = path or project_root or "."
        if not os.path.isabs(search_root) and project_root:
            search_root = os.path.join(project_root, search_root)

        if not os.path.isdir(search_root):
            return {"error": f"Directory not found: {search_root}"}

        matches: list[str] = []
        try:
            for root, _dirs, files in os.walk(search_root):
                for filename in files:
                    full = os.path.join(root, filename)
                    rel = os.path.relpath(full, project_root or search_root).replace("\\", "/")
                    if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(filename, pattern):
                        matches.append(rel)

            matches.sort()
            return {"pattern": pattern, "matches": matches[:200], "total": len(matches)}
        except Exception as e:
            return {"error": f"Glob failed: {e}"}

    return ToolDefinition(
        name="glob",
        description="Find files matching a glob pattern. Returns relative paths.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py', 'src/*.ts')"},
                "path": {"type": "string", "description": "Directory to search in (default: project root)"},
            },
            "required": ["pattern"],
        },
        handler=handler,
    )


def create_grep_tool(project_root: str = "") -> ToolDefinition:
    """Create the grep tool for searching file contents.

    :param project_root: Project root for path resolution.
    :returns: ToolDefinition for grep.
    """

    def handler(*, pattern: str, path: str = "", file_pattern: str = "") -> dict[str, Any]:
        search_root = path or project_root or "."
        if not os.path.isabs(search_root) and project_root:
            search_root = os.path.join(project_root, search_root)

        if not os.path.isdir(search_root):
            return {"error": f"Directory not found: {search_root}"}

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

        results: list[dict[str, Any]] = []
        try:
            for root, _dirs, files in os.walk(search_root):
                for filename in files:
                    if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                        continue
                    full = os.path.join(root, filename)
                    rel = os.path.relpath(full, project_root or search_root).replace("\\", "/")
                    try:
                        with open(full, encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    results.append(
                                        {
                                            "file": rel,
                                            "line": line_num,
                                            "text": line.rstrip()[:200],
                                        }
                                    )
                                    if len(results) >= 100:
                                        return {
                                            "pattern": pattern,
                                            "matches": results,
                                            "total": len(results),
                                            "truncated": True,
                                        }
                    except (OSError, UnicodeDecodeError):
                        continue

            return {"pattern": pattern, "matches": results, "total": len(results), "truncated": False}
        except Exception as e:
            return {"error": f"Grep failed: {e}"}

    return ToolDefinition(
        name="grep",
        description="Search file contents using regex. Returns matching lines with file paths and line numbers.",
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {"type": "string", "description": "Directory to search in (default: project root)"},
                "file_pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
        handler=handler,
    )
