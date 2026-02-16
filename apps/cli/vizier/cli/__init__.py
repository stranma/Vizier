"""Vizier CLI application."""

__version__ = "0.7.0"

import click

from vizier.cli.daemon_commands import daemon_init, daemon_register, daemon_start, daemon_status, daemon_stop
from vizier.cli.spec_commands import spec


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Vizier: autonomous multi-agent work system."""


main.add_command(spec)
main.add_command(daemon_init, "init")
main.add_command(daemon_register, "register")
main.add_command(daemon_start, "start")
main.add_command(daemon_stop, "stop")
main.add_command(daemon_status, "status")
