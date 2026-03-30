"""Vizier CLI -- province lifecycle management.

Commands::

    vizier create <firman> [--berat <berat>] [--name <name>]
    vizier list
    vizier status <province>
    vizier stop <province>
    vizier start <province>
    vizier destroy <province>
    vizier logs <province>
"""

import click


@click.group()
def main() -> None:
    """Vizier -- province orchestration for Sultanate."""


@main.command()
@click.argument("firman")
@click.option("--berat", default=None, help="Berat (agent profile) to use.")
@click.option("--name", default=None, help="Province name.")
def create(firman: str, berat: str | None, name: str | None) -> None:
    """Create a province from a firman."""
    raise NotImplementedError


@main.command("list")
def list_provinces() -> None:
    """List all provinces with status."""
    raise NotImplementedError


@main.command()
@click.argument("province")
def status(province: str) -> None:
    """Show detailed province status."""
    raise NotImplementedError


@main.command()
@click.argument("province")
def stop(province: str) -> None:
    """Stop a running province."""
    raise NotImplementedError


@main.command()
@click.argument("province")
def start(province: str) -> None:
    """Start a stopped province."""
    raise NotImplementedError


@main.command()
@click.argument("province")
def destroy(province: str) -> None:
    """Destroy a province and clean up."""
    raise NotImplementedError


@main.command()
@click.argument("province")
def logs(province: str) -> None:
    """View province logs."""
    raise NotImplementedError
