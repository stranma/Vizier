"""Vizier CLI application."""

__version__ = "0.1.0"

import click

from vizier.cli.spec_commands import spec


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Vizier: autonomous multi-agent work system."""


main.add_command(spec)
