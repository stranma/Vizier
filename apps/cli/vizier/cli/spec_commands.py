"""CLI commands for spec management: create and ready."""

from __future__ import annotations

from pathlib import Path

import click

from vizier.core.file_protocol.spec_io import create_spec, list_specs, update_spec_status
from vizier.core.models.spec import SpecStatus


def _find_project_root() -> str:
    """Find the project root by looking for .vizier/ directory."""
    current = Path.cwd()
    while current != current.parent:
        if (current / ".vizier").is_dir():
            return str(current)
        current = current.parent
    return str(Path.cwd())


def _generate_spec_id(project_root: str, description: str) -> str:
    """Generate a sequential spec ID from the description."""
    existing = list_specs(project_root)
    max_num = 0
    for spec in existing:
        parts = spec.frontmatter.id.split("-", 1)
        try:
            num = int(parts[0])
            if num > max_num:
                max_num = num
        except (ValueError, IndexError):
            pass

    next_num = max_num + 1
    slug = description.lower().replace(" ", "-")[:40]
    slug = "".join(c for c in slug if c.isalnum() or c == "-")
    slug = slug.strip("-")
    if not slug:
        slug = "task"

    return f"{next_num:03d}-{slug}"


@click.group()
def spec() -> None:
    """Manage specs (create, ready, list)."""


@spec.command("create")
@click.argument("description")
@click.option("--project", "-p", default=None, help="Project root directory (auto-detected if omitted).")
@click.option("--plugin", default="software", help="Plugin name for the spec.")
@click.option("--priority", default=1, type=int, help="Spec priority (lower = higher).")
@click.option("--complexity", default="medium", type=click.Choice(["low", "medium", "high"]))
def spec_create(
    description: str,
    project: str | None,
    plugin: str,
    priority: int,
    complexity: str,
) -> None:
    """Create a DRAFT spec from a task description."""
    project_root = project or _find_project_root()
    vizier_dir = Path(project_root) / ".vizier"
    if not vizier_dir.exists():
        vizier_dir.mkdir(parents=True)
        specs_dir = vizier_dir / "specs"
        specs_dir.mkdir()

    spec_id = _generate_spec_id(project_root, description)

    result = create_spec(
        project_root,
        spec_id,
        description,
        {
            "status": "DRAFT",
            "priority": priority,
            "complexity": complexity,
            "plugin": plugin,
        },
    )

    click.echo(f"Created spec: {result.frontmatter.id}")
    click.echo(f"Status: {result.frontmatter.status}")
    click.echo(f"Path: {result.file_path}")


@spec.command("ready")
@click.argument("spec_id")
@click.option("--project", "-p", default=None, help="Project root directory.")
def spec_ready(spec_id: str, project: str | None) -> None:
    """Transition a DRAFT spec to READY for processing."""
    project_root = project or _find_project_root()

    specs = list_specs(project_root)
    target = None
    for s in specs:
        if s.frontmatter.id == spec_id:
            target = s
            break

    if target is None:
        click.echo(f"Spec not found: {spec_id}", err=True)
        raise SystemExit(1)

    if target.file_path is None:
        click.echo(f"Spec has no file path: {spec_id}", err=True)
        raise SystemExit(1)

    if target.frontmatter.status != SpecStatus.DRAFT:
        click.echo(
            f"Spec {spec_id} is {target.frontmatter.status}, not DRAFT. Only DRAFT specs can be made READY.",
            err=True,
        )
        raise SystemExit(1)

    update_spec_status(target.file_path, SpecStatus.READY)
    click.echo(f"Spec {spec_id} is now READY")


@spec.command("list")
@click.option("--project", "-p", default=None, help="Project root directory.")
@click.option("--status", "-s", default=None, help="Filter by status (e.g. READY, DRAFT).")
def spec_list(project: str | None, status: str | None) -> None:
    """List all specs in the project."""
    project_root = project or _find_project_root()

    status_filter = None
    if status:
        try:
            status_filter = SpecStatus(status.upper())
        except ValueError:
            click.echo(f"Invalid status: {status}", err=True)
            raise SystemExit(1) from None

    specs = list_specs(project_root, status_filter=status_filter)

    if not specs:
        click.echo("No specs found.")
        return

    for s in specs:
        priority_str = f"P{s.frontmatter.priority}"
        click.echo(f"  {s.frontmatter.id}  [{s.frontmatter.status}]  {priority_str}  {s.frontmatter.complexity}")
