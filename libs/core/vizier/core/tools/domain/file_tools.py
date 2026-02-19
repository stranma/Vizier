"""File operation tools: read_file, write_file, edit_file."""

from __future__ import annotations

import os
from typing import Any

from vizier.core.runtime.types import ToolDefinition
from vizier.core.tools.domain.write_set import WriteSetChecker  # noqa: TC001


def create_read_file_tool(project_root: str = "") -> ToolDefinition:
    """Create the read_file tool.

    :param project_root: Project root for path resolution.
    :returns: ToolDefinition for read_file.
    """

    def handler(*, path: str) -> dict[str, Any]:
        full_path = _resolve_path(path, project_root)
        if not os.path.isfile(full_path):
            return {"error": f"File not found: {path}"}
        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
            return {"path": path, "content": content, "size": len(content)}
        except Exception as e:
            return {"error": f"Failed to read {path}: {e}"}

    return ToolDefinition(
        name="read_file",
        description="Read the contents of a file. Returns the file content as a string.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read (relative to project root)"},
            },
            "required": ["path"],
        },
        handler=handler,
    )


def create_write_file_tool(
    project_root: str = "",
    write_set: WriteSetChecker | None = None,
) -> ToolDefinition:
    """Create the write_file tool with write-set enforcement.

    :param project_root: Project root for path resolution.
    :param write_set: Write-set checker for boundary enforcement (D55).
    :returns: ToolDefinition for write_file.
    """

    def handler(*, path: str, content: str) -> dict[str, Any]:
        if write_set and not write_set.is_allowed(path):
            return {"error": f"Write denied: {path} is outside the write-set boundary"}
        full_path = _resolve_path(path, project_root)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"path": path, "bytes_written": len(content.encode("utf-8"))}
        except Exception as e:
            return {"error": f"Failed to write {path}: {e}"}

    return ToolDefinition(
        name="write_file",
        description="Write content to a file. Creates parent directories if needed. Enforces write-set boundaries.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write (relative to project root)"},
                "content": {"type": "string", "description": "Content to write to the file"},
            },
            "required": ["path", "content"],
        },
        handler=handler,
    )


def create_edit_file_tool(
    project_root: str = "",
    write_set: WriteSetChecker | None = None,
) -> ToolDefinition:
    """Create the edit_file tool with write-set enforcement.

    :param project_root: Project root for path resolution.
    :param write_set: Write-set checker for boundary enforcement (D55).
    :returns: ToolDefinition for edit_file.
    """

    def handler(*, path: str, old_text: str, new_text: str) -> dict[str, Any]:
        if write_set and not write_set.is_allowed(path):
            return {"error": f"Edit denied: {path} is outside the write-set boundary"}
        full_path = _resolve_path(path, project_root)
        if not os.path.isfile(full_path):
            return {"error": f"File not found: {path}"}
        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return {"error": f"Text to replace not found in {path}"}
            count = content.count(old_text)
            if count > 1:
                return {"error": f"Text to replace appears {count} times in {path}. Must be unique."}
            new_content = content.replace(old_text, new_text, 1)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return {"path": path, "replacements": 1}
        except Exception as e:
            return {"error": f"Failed to edit {path}: {e}"}

    return ToolDefinition(
        name="edit_file",
        description="Replace a unique text string in a file. The old_text must appear exactly once.",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit (relative to project root)"},
                "old_text": {"type": "string", "description": "Exact text to find and replace (must be unique)"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
        handler=handler,
    )


def _resolve_path(path: str, project_root: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    if project_root:
        return os.path.join(project_root, path)
    return path
