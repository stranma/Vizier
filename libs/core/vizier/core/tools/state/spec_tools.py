"""Spec CRUD tools wrapping file_protocol.spec_io with Contract C invariants."""

from __future__ import annotations

import json
import os
from typing import Any

from vizier.core.file_protocol.spec_io import (
    create_spec,
    list_specs,
    read_spec,
    update_spec_status,
)
from vizier.core.models.spec import SpecStatus
from vizier.core.runtime.types import ToolDefinition


def create_create_spec_tool(project_root: str = "") -> ToolDefinition:
    """Create the create_spec tool.

    :param project_root: Project root for spec storage.
    :returns: ToolDefinition for create_spec.
    """

    def handler(*, spec_id: str, content: str, frontmatter: str = "{}") -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            overrides = json.loads(frontmatter) if frontmatter != "{}" else None
        except json.JSONDecodeError as e:
            return {"error": f"Invalid frontmatter JSON: {e}"}
        try:
            spec = create_spec(project_root, spec_id, content, overrides)
            return {
                "spec_id": spec.frontmatter.id,
                "status": spec.frontmatter.status.value,
                "file_path": spec.file_path or "",
            }
        except Exception as e:
            return {"error": f"Failed to create spec: {e}"}

    return ToolDefinition(
        name="create_spec",
        description="Create a new spec file with YAML frontmatter and markdown content. Returns the created spec ID and path.",
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier (e.g. '001-feature-name')"},
                "content": {"type": "string", "description": "Markdown body of the spec"},
                "frontmatter": {
                    "type": "string",
                    "description": "JSON string of additional frontmatter fields (e.g. priority, complexity, parent, depends_on)",
                    "default": "{}",
                },
            },
            "required": ["spec_id", "content"],
        },
        handler=handler,
    )


def create_read_spec_tool(project_root: str = "") -> ToolDefinition:
    """Create the read_spec tool.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for read_spec.
    """

    def handler(*, spec_path: str) -> dict[str, Any]:
        full_path = _resolve_spec_path(spec_path, project_root)
        try:
            spec = read_spec(full_path)
            return {
                "spec_id": spec.frontmatter.id,
                "status": spec.frontmatter.status.value,
                "priority": spec.frontmatter.priority,
                "complexity": spec.frontmatter.complexity.value,
                "parent": spec.frontmatter.parent,
                "depends_on": spec.frontmatter.depends_on,
                "plugin": spec.frontmatter.plugin,
                "content": spec.content,
                "file_path": spec.file_path or "",
            }
        except FileNotFoundError:
            return {"error": f"Spec not found: {spec_path}"}
        except Exception as e:
            return {"error": f"Failed to read spec: {e}"}

    return ToolDefinition(
        name="read_spec",
        description="Read a spec file and return its frontmatter and content.",
        input_schema={
            "type": "object",
            "properties": {
                "spec_path": {
                    "type": "string",
                    "description": "Path to the spec.md file (absolute or relative to project root)",
                },
            },
            "required": ["spec_path"],
        },
        handler=handler,
    )


def create_update_spec_status_tool(project_root: str = "") -> ToolDefinition:
    """Create the update_spec_status tool with Contract C invariant checking.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for update_spec_status.
    """

    def handler(*, spec_path: str, new_status: str, extra_updates: str = "{}") -> dict[str, Any]:
        full_path = _resolve_spec_path(spec_path, project_root)
        try:
            status = SpecStatus(new_status)
        except ValueError:
            valid = [s.value for s in SpecStatus]
            return {"error": f"Invalid status '{new_status}'. Valid: {valid}"}
        try:
            extras = json.loads(extra_updates) if extra_updates != "{}" else None
        except json.JSONDecodeError as e:
            return {"error": f"Invalid extra_updates JSON: {e}"}
        try:
            spec = update_spec_status(full_path, status, extras)
            return {
                "spec_id": spec.frontmatter.id,
                "status": spec.frontmatter.status.value,
                "file_path": spec.file_path or "",
            }
        except FileNotFoundError:
            return {"error": f"Spec not found: {spec_path}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Failed to update spec: {e}"}

    return ToolDefinition(
        name="update_spec_status",
        description=(
            "Transition a spec to a new status. Enforces valid transitions per Contract C. "
            "Allowed transitions: DRAFT->SCOUTED/READY/DECOMPOSED, SCOUTED->DECOMPOSED, "
            "READY->IN_PROGRESS, IN_PROGRESS->REVIEW/STUCK/INTERRUPTED, "
            "REVIEW->DONE/REJECTED, REJECTED->IN_PROGRESS, STUCK->DECOMPOSED, INTERRUPTED->READY."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "spec_path": {
                    "type": "string",
                    "description": "Path to the spec.md file (absolute or relative to project root)",
                },
                "new_status": {
                    "type": "string",
                    "description": "Target status (DRAFT, SCOUTED, READY, IN_PROGRESS, REVIEW, DONE, REJECTED, STUCK, DECOMPOSED, INTERRUPTED)",
                },
                "extra_updates": {
                    "type": "string",
                    "description": "JSON string of additional frontmatter updates (e.g. assigned_to, retries)",
                    "default": "{}",
                },
            },
            "required": ["spec_path", "new_status"],
        },
        handler=handler,
    )


def create_list_specs_tool(project_root: str = "") -> ToolDefinition:
    """Create the list_specs tool.

    :param project_root: Project root for spec listing.
    :returns: ToolDefinition for list_specs.
    """

    def handler(*, status_filter: str = "") -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        status = None
        if status_filter:
            try:
                status = SpecStatus(status_filter)
            except ValueError:
                valid = [s.value for s in SpecStatus]
                return {"error": f"Invalid status filter '{status_filter}'. Valid: {valid}"}
        try:
            specs = list_specs(project_root, status)
            return {
                "specs": [
                    {
                        "spec_id": s.frontmatter.id,
                        "status": s.frontmatter.status.value,
                        "priority": s.frontmatter.priority,
                        "complexity": s.frontmatter.complexity.value,
                        "parent": s.frontmatter.parent,
                        "depends_on": s.frontmatter.depends_on,
                        "file_path": s.file_path or "",
                    }
                    for s in specs
                ],
                "total": len(specs),
            }
        except Exception as e:
            return {"error": f"Failed to list specs: {e}"}

    return ToolDefinition(
        name="list_specs",
        description="List all specs in the project, optionally filtered by status.",
        input_schema={
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "description": "Optional status to filter by (e.g. 'READY', 'IN_PROGRESS')",
                    "default": "",
                },
            },
            "required": [],
        },
        handler=handler,
    )


def create_write_feedback_tool(project_root: str = "") -> ToolDefinition:
    """Create the write_feedback tool for storing review feedback on a spec.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for write_feedback.
    """

    def handler(*, spec_id: str, feedback: str, author: str = "") -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        feedback_dir = os.path.join(project_root, ".vizier", "specs", spec_id, "feedback")
        try:
            os.makedirs(feedback_dir, exist_ok=True)
            existing = [f for f in os.listdir(feedback_dir) if f.endswith(".md")]
            index = len(existing) + 1
            filename = f"feedback-{index:03d}.md"
            filepath = os.path.join(feedback_dir, filename)
            header = f"# Feedback #{index}"
            if author:
                header += f" (by {author})"
            header += "\n\n"
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(header + feedback)
            return {
                "spec_id": spec_id,
                "feedback_file": filename,
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write feedback: {e}"}

    return ToolDefinition(
        name="write_feedback",
        description="Write review feedback for a spec. Stored in specs/<id>/feedback/ directory.",
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier"},
                "feedback": {"type": "string", "description": "Feedback content (markdown)"},
                "author": {
                    "type": "string",
                    "description": "Who wrote the feedback (e.g. 'quality_gate', 'pasha')",
                    "default": "",
                },
            },
            "required": ["spec_id", "feedback"],
        },
        handler=handler,
    )


def _resolve_spec_path(path: str, project_root: str) -> str:
    """Resolve a spec path against the project root."""
    if os.path.isabs(path):
        return path
    if project_root:
        return os.path.join(project_root, path)
    return path
