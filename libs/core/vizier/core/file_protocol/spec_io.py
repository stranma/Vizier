"""Spec file I/O: create, read, update, list spec files."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import frontmatter

from vizier.core.models.spec import VALID_TRANSITIONS, Spec, SpecFrontmatter, SpecStatus


def _specs_dir(project_root: str | Path) -> Path:
    return Path(project_root) / ".vizier" / "specs"


def create_spec(
    project_root: str | Path,
    spec_id: str,
    content: str,
    frontmatter_overrides: dict | None = None,
) -> Spec:
    """Create a new spec file on disk.

    :param project_root: Root directory of the project (contains .vizier/).
    :param spec_id: Spec identifier (e.g. "001-feature-name").
    :param content: Markdown body of the spec.
    :param frontmatter_overrides: Additional frontmatter fields to set.
    :returns: The created Spec object.
    """
    overrides = frontmatter_overrides or {}
    now = datetime.utcnow()
    fm_data = {"id": spec_id, "created": now, "updated": now, **overrides}
    fm = SpecFrontmatter.model_validate(fm_data)

    spec_dir = _specs_dir(project_root) / spec_id
    spec_dir.mkdir(parents=True, exist_ok=True)
    spec_path = spec_dir / "spec.md"

    post = frontmatter.Post(content, handler=frontmatter.YAMLHandler(), **fm.model_dump(mode="json"))
    tmp_path = spec_path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    os.replace(str(tmp_path), str(spec_path))

    return Spec(frontmatter=fm, content=content, file_path=str(spec_path))


def read_spec(spec_path: str | Path) -> Spec:
    """Read and parse a spec file from disk.

    :param spec_path: Path to the spec.md file.
    :returns: Parsed Spec object.
    :raises FileNotFoundError: If the spec file does not exist.
    """
    path = Path(spec_path)
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_path}")

    post = frontmatter.load(str(path))
    fm = SpecFrontmatter.model_validate(dict(post.metadata))
    return Spec(frontmatter=fm, content=post.content, file_path=str(path))


def update_spec_status(
    spec_path: str | Path,
    new_status: SpecStatus,
    extra_updates: dict | None = None,
) -> Spec:
    """Update spec status with transition validation.

    :param spec_path: Path to the spec.md file.
    :param new_status: Target status.
    :param extra_updates: Additional frontmatter fields to update (e.g. assigned_to, retries).
    :returns: Updated Spec object.
    :raises ValueError: If the transition is not valid per VALID_TRANSITIONS.
    :raises FileNotFoundError: If the spec file does not exist.
    """
    spec = read_spec(spec_path)
    current = spec.frontmatter.status

    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(f"Invalid transition: {current} -> {new_status}. Allowed: {allowed}")

    updates = extra_updates or {}
    updates["status"] = new_status
    updates["updated"] = datetime.utcnow()

    path = Path(spec_path)
    post = frontmatter.load(str(path))
    for key, value in updates.items():
        if isinstance(value, datetime):
            post.metadata[key] = value.isoformat()
        elif hasattr(value, "value"):
            post.metadata[key] = value.value
        else:
            post.metadata[key] = value

    tmp_path = path.with_suffix(".md.tmp")
    tmp_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    os.replace(str(tmp_path), str(path))
    return read_spec(spec_path)


def list_specs(
    project_root: str | Path,
    status_filter: SpecStatus | None = None,
) -> list[Spec]:
    """List all specs in a project, optionally filtered by status.

    :param project_root: Root directory of the project.
    :param status_filter: If set, only return specs matching this status.
    :returns: List of Spec objects.
    """
    specs_dir = _specs_dir(project_root)
    if not specs_dir.exists():
        return []

    results: list[Spec] = []
    for entry in sorted(specs_dir.iterdir()):
        if not entry.is_dir():
            continue
        spec_file = entry / "spec.md"
        if not spec_file.exists():
            continue
        spec = read_spec(spec_file)
        if status_filter is None or spec.frontmatter.status == status_filter:
            results.append(spec)

    for entry in sorted(specs_dir.iterdir()):
        if not entry.is_dir():
            continue
        for sub_entry in sorted(entry.iterdir()):
            if (
                sub_entry.is_file()
                and sub_entry.name != "spec.md"
                and sub_entry.suffix == ".md"
                and sub_entry.parent.name != "feedback"
                and not sub_entry.name.startswith(".")
            ):
                try:
                    spec = read_spec(sub_entry)
                    if status_filter is None or spec.frontmatter.status == status_filter:
                        results.append(spec)
                except Exception:
                    pass

    seen_ids: set[str] = set()
    unique: list[Spec] = []
    for spec in results:
        if spec.frontmatter.id not in seen_ids:
            seen_ids.add(spec.frontmatter.id)
            unique.append(spec)
    return unique
