"""Spec CRUD + state machine tools.

Implements the 6 spec lifecycle MCP tools:
- spec_create: create a spec in DRAFT state
- spec_read: read spec contents and metadata
- spec_list: list specs with optional status filter
- spec_transition: validate and execute state transitions
- spec_update: update mutable spec fields
- spec_write_feedback: write QG feedback or rejection reason

Filesystem layout per ARCHITECTURE.md section 3.4:
  {projects_dir}/{project_id}/specs/{spec_id}/spec.md
  {projects_dir}/{project_id}/specs/{spec_id}/feedback/
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import tempfile
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import yaml

from vizier_mcp.models.spec import (
    VALID_TRANSITIONS,
    Spec,
    SpecFeedback,
    SpecMetadata,
    SpecStatus,
    SpecSummary,
    is_valid_transition,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

logger = logging.getLogger(__name__)

FRONTMATTER_SEPARATOR = "---"

_MUTABLE_FIELDS = {"retry_count", "assigned_agent", "complexity", "claimed_at", "depends_on"}


def _specs_dir(config: ServerConfig, project_id: str) -> Path:
    """Return the specs directory for a project."""
    assert config.projects_dir is not None
    return config.projects_dir / project_id / "specs"


def _spec_dir(config: ServerConfig, project_id: str, spec_id: str) -> Path:
    """Return the directory for a specific spec, with path containment check."""
    specs_path = _specs_dir(config, project_id)
    result = specs_path / spec_id
    if not str(result.resolve()).startswith(str(specs_path.resolve())):
        raise ValueError(f"Spec ID escapes project directory: {spec_id}")
    return result


def _spec_file(config: ServerConfig, project_id: str, spec_id: str) -> Path:
    """Return the spec.md file path."""
    return _spec_dir(config, project_id, spec_id) / "spec.md"


def _feedback_dir(config: ServerConfig, project_id: str, spec_id: str) -> Path:
    """Return the feedback directory for a spec."""
    return _spec_dir(config, project_id, spec_id) / "feedback"


def _serialize_spec(spec: Spec) -> str:
    """Serialize a Spec to frontmatter + body markdown format."""
    meta_dict = spec.metadata.model_dump(mode="json")
    frontmatter = yaml.dump(meta_dict, default_flow_style=False, sort_keys=False)
    parts = [
        FRONTMATTER_SEPARATOR,
        frontmatter.rstrip(),
        FRONTMATTER_SEPARATOR,
        "",
    ]
    if spec.artifacts:
        parts.append("## Artifacts")
        for a in spec.artifacts:
            parts.append(f"- {a}")
        parts.append("")
    if spec.criteria:
        parts.append("## Acceptance Criteria")
        for c in spec.criteria:
            parts.append(f"- {c}")
        parts.append("")
    if spec.body:
        parts.append(spec.body)
    return "\n".join(parts)


def _parse_spec(content: str) -> tuple[dict, str, list[str], list[str]]:
    """Parse frontmatter + body markdown into (metadata_dict, body, artifacts, criteria)."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != FRONTMATTER_SEPARATOR:
        raise ValueError("Spec file missing frontmatter separator")

    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_SEPARATOR:
            end_idx = i
            break
    if end_idx == -1:
        raise ValueError("Spec file missing closing frontmatter separator")

    frontmatter_text = "\n".join(lines[1:end_idx])
    meta_dict = yaml.safe_load(frontmatter_text) or {}

    remaining = "\n".join(lines[end_idx + 1 :])
    artifacts: list[str] = []
    criteria: list[str] = []
    body_lines: list[str] = []
    current_section: str | None = None

    for line in remaining.split("\n"):
        stripped = line.strip()
        if stripped == "## Artifacts":
            current_section = "artifacts"
            continue
        elif stripped == "## Acceptance Criteria":
            current_section = "criteria"
            continue
        elif stripped.startswith("## "):
            current_section = "body"

        if current_section == "artifacts" and stripped.startswith("- "):
            artifacts.append(stripped[2:])
        elif current_section == "criteria" and stripped.startswith("- "):
            criteria.append(stripped[2:])
        elif current_section == "body" or (current_section is None and stripped):
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    return meta_dict, body, artifacts, criteria


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically using write-then-rename (D40).

    :param path: Target file path.
    :param content: Content to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _compute_next_seq(specs_path: Path) -> str:
    """Compute the next 3-digit sequence number from existing spec directories.

    Supports up to 999 specs per project.
    """
    if not specs_path.exists():
        return "001"
    existing = sorted(
        (d.name for d in specs_path.iterdir() if d.is_dir() and d.name[:3].isdigit()),
        key=lambda n: int(n.split("-")[0]),
    )
    if not existing:
        return "001"
    last_num = int(existing[-1].split("-")[0])
    return f"{last_num + 1:03d}"


def _sanitize_slug(title: str) -> str:
    """Create a filesystem-safe slug from a title."""
    slug = title.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug[:40]


def spec_create(
    config: ServerConfig,
    project_id: str,
    title: str,
    description: str,
    complexity: str = "MEDIUM",
    artifacts: list[str] | None = None,
    criteria: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict:
    """Create a new spec in DRAFT state.

    Uses atomic directory creation (os.mkdir) for race-safe ID generation.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param title: Spec title.
    :param description: Spec body/description.
    :param complexity: LOW, MEDIUM, or HIGH.
    :param artifacts: List of artifact paths.
    :param criteria: List of acceptance criteria.
    :param depends_on: List of spec IDs this depends on.
    :return: {"spec_id": str, "path": str}
    """
    slug = _sanitize_slug(title)
    specs_path = _specs_dir(config, project_id)
    specs_path.mkdir(parents=True, exist_ok=True)

    for _ in range(10):
        seq = _compute_next_seq(specs_path)
        spec_id = f"{seq}-{slug}"
        spec_dir = specs_path / spec_id
        try:
            spec_dir.mkdir(parents=False)
            break
        except FileExistsError:
            continue
    else:
        return {"error": "Failed to allocate spec ID after 10 attempts"}

    now = datetime.now(UTC)
    metadata = SpecMetadata(
        spec_id=spec_id,
        project_id=project_id,
        title=title,
        status=SpecStatus.DRAFT,
        complexity=complexity,
        created_at=now,
        updated_at=now,
        depends_on=depends_on or [],
    )
    spec = Spec(
        metadata=metadata,
        body=description,
        artifacts=artifacts or [],
        criteria=criteria or [],
    )

    spec_path = _spec_file(config, project_id, spec_id)
    _atomic_write(spec_path, _serialize_spec(spec))

    feedback_path = _feedback_dir(config, project_id, spec_id)
    feedback_path.mkdir(parents=True, exist_ok=True)

    return {"spec_id": spec_id, "path": str(spec_path)}


def spec_read(config: ServerConfig, project_id: str, spec_id: str) -> dict:
    """Read spec contents and metadata.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :return: Spec data as dict with metadata, body, artifacts, criteria.
    """
    spec_path = _spec_file(config, project_id, spec_id)
    if not spec_path.exists():
        return {"error": f"Spec not found: {spec_id}"}

    content = spec_path.read_text()
    meta_dict, body, artifacts, criteria = _parse_spec(content)
    metadata = SpecMetadata(**meta_dict)
    spec = Spec(metadata=metadata, body=body, artifacts=artifacts, criteria=criteria)
    return spec.model_dump(mode="json")


def spec_list(
    config: ServerConfig,
    project_id: str,
    status_filter: str | None = None,
) -> dict:
    """List specs with optional status filter.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param status_filter: Optional SpecStatus value to filter by.
    :return: {"specs": list[SpecSummary]}
    """
    specs_path = _specs_dir(config, project_id)
    if not specs_path.exists():
        return {"specs": []}

    summaries: list[dict] = []
    for spec_dir in sorted(specs_path.iterdir()):
        if not spec_dir.is_dir():
            continue
        spec_file = spec_dir / "spec.md"
        if not spec_file.exists():
            continue
        try:
            content = spec_file.read_text()
            meta_dict, _, _, _ = _parse_spec(content)
            metadata = SpecMetadata(**meta_dict)
        except (ValueError, yaml.YAMLError) as exc:
            logger.warning("Skipping corrupt spec at %s: %s", spec_file, exc)
            continue

        if status_filter and metadata.status.value != status_filter:
            continue

        summary = SpecSummary(
            spec_id=metadata.spec_id,
            project_id=metadata.project_id,
            title=metadata.title,
            status=metadata.status,
            complexity=metadata.complexity,
            retry_count=metadata.retry_count,
            assigned_agent=metadata.assigned_agent,
        )
        summaries.append(summary.model_dump(mode="json"))

    return {"specs": summaries}


def spec_transition(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    new_status: str,
    agent_role: str,
) -> dict:
    """Validate and execute a state transition.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param new_status: Target status string.
    :param agent_role: Role of the agent requesting the transition.
    :return: {"success": bool, "error"?: str, "from_status"?: str, "to_status"?: str}
    """
    spec_path = _spec_file(config, project_id, spec_id)
    if not spec_path.exists():
        return {"success": False, "error": f"Spec not found: {spec_id}"}

    try:
        target = SpecStatus(new_status)
    except ValueError:
        valid = [s.value for s in SpecStatus]
        return {"success": False, "error": f"Invalid status: {new_status}. Valid: {valid}"}

    content = spec_path.read_text()
    meta_dict, body, artifacts, criteria = _parse_spec(content)
    metadata = SpecMetadata(**meta_dict)
    current = metadata.status

    if not is_valid_transition(current, target):
        allowed = [s.value for s in VALID_TRANSITIONS.get(current, [])]
        return {
            "success": False,
            "error": f"Invalid transition: {current.value} -> {target.value}. Allowed from {current.value}: {allowed}",
        }

    now = datetime.now(UTC)
    metadata.status = target
    metadata.updated_at = now

    if target == SpecStatus.IN_PROGRESS:
        metadata.claimed_at = now
        metadata.assigned_agent = agent_role

    if target == SpecStatus.READY and current == SpecStatus.REJECTED:
        metadata.retry_count += 1

    if target == SpecStatus.READY and current == SpecStatus.INTERRUPTED:
        metadata.retry_count += 1

    spec = Spec(metadata=metadata, body=body, artifacts=artifacts, criteria=criteria)
    _atomic_write(spec_path, _serialize_spec(spec))

    return {
        "success": True,
        "from_status": current.value,
        "to_status": target.value,
    }


def spec_update(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    fields: dict,
) -> dict:
    """Update mutable spec fields.

    Updatable fields: retry_count, assigned_agent, complexity, claimed_at, depends_on.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param fields: Dict of field names to new values.
    :return: {"success": bool, "updated_fields": list[str]} or {"error": str}
    """
    spec_path = _spec_file(config, project_id, spec_id)
    if not spec_path.exists():
        return {"error": f"Spec not found: {spec_id}"}

    invalid = set(fields.keys()) - _MUTABLE_FIELDS
    if invalid:
        return {"error": f"Cannot update immutable fields: {invalid}. Mutable: {_MUTABLE_FIELDS}"}

    content = spec_path.read_text()
    meta_dict, body, artifacts, criteria = _parse_spec(content)
    metadata = SpecMetadata(**meta_dict)

    updated: list[str] = []
    for key, value in fields.items():
        setattr(metadata, key, value)
        updated.append(key)

    metadata.updated_at = datetime.now(UTC)
    spec = Spec(metadata=metadata, body=body, artifacts=artifacts, criteria=criteria)
    _atomic_write(spec_path, _serialize_spec(spec))

    return {"success": True, "updated_fields": updated}


def spec_write_feedback(
    config: ServerConfig,
    project_id: str,
    spec_id: str,
    verdict: str,
    feedback: str,
    reviewer: str = "quality_gate",
) -> dict:
    """Write QG feedback or rejection reason.

    :param config: Server configuration.
    :param project_id: Project identifier.
    :param spec_id: Spec identifier.
    :param verdict: ACCEPT or REJECT.
    :param feedback: Detailed feedback text.
    :param reviewer: Agent writing the feedback.
    :return: {"path": str} or {"error": str}
    """
    valid_verdicts = {"ACCEPT", "REJECT"}
    if verdict not in valid_verdicts:
        return {"error": f"Invalid verdict: {verdict}. Must be one of: {valid_verdicts}"}

    spec_path = _spec_file(config, project_id, spec_id)
    if not spec_path.exists():
        return {"error": f"Spec not found: {spec_id}"}

    fb = SpecFeedback(
        spec_id=spec_id,
        verdict=verdict,
        feedback=feedback,
        reviewer=reviewer,
    )

    fb_dir = _feedback_dir(config, project_id, spec_id)
    fb_dir.mkdir(parents=True, exist_ok=True)

    timestamp = fb.created_at.strftime("%Y%m%dT%H%M%S%f")
    fb_file = fb_dir / f"{timestamp}-{verdict.lower()}.json"
    counter = 1
    while fb_file.exists():
        fb_file = fb_dir / f"{timestamp}-{verdict.lower()}-{counter}.json"
        counter += 1
    _atomic_write(fb_file, json.dumps(fb.model_dump(mode="json"), indent=2))

    return {"path": str(fb_file)}
