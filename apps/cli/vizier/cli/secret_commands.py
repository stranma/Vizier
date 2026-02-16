"""CLI commands for secret management: list, check, set."""

from __future__ import annotations

import os
from pathlib import Path

import click


def _default_root() -> str:
    return os.environ.get("VIZIER_ROOT", "/opt/vizier")


@click.group("secret")
def secret() -> None:
    """Manage Vizier secrets."""


@secret.command("list")
@click.option("--root", default=None, help="Vizier root directory.")
def secret_list(root: str | None) -> None:
    """List all configured secret names."""
    vizier_root = root or _default_root()

    from vizier.core.secrets.startup import create_secret_store

    store = create_secret_store(vizier_root)
    keys = store.keys()

    if not keys:
        click.echo("No secrets configured.")
        click.echo(f"Add secrets to {Path(vizier_root) / '.env'} or configure Azure Key Vault.")
        return

    click.echo(f"Configured secrets ({len(keys)}):")
    for key in keys:
        has_value = store.is_non_empty(key)
        status = "set" if has_value else "empty"
        click.echo(f"  {key} [{status}]")


@secret.command("check")
@click.argument("key")
@click.option("--root", default=None, help="Vizier root directory.")
def secret_check(key: str, root: str | None) -> None:
    """Check whether a specific secret is configured."""
    vizier_root = root or _default_root()

    from vizier.core.secrets.startup import create_secret_store

    store = create_secret_store(vizier_root)

    exists = store.has(key)
    has_value = store.is_non_empty(key)

    click.echo(f"Secret: {key}")
    click.echo(f"  Exists: {'yes' if exists else 'no'}")
    click.echo(f"  Has value: {'yes' if has_value else 'no'}")

    if not exists:
        click.echo(f"\nTo configure: add {key}=<value> to {Path(vizier_root) / '.env'}")


@secret.command("set")
@click.argument("key")
@click.option("--root", default=None, help="Vizier root directory.")
def secret_set(key: str, root: str | None) -> None:
    """Set a secret value (stored in .env file)."""
    vizier_root = root or _default_root()
    env_path = Path(vizier_root) / ".env"

    value = click.prompt(f"Enter value for {key}", hide_input=True, default="", show_default=False)
    if not value:
        click.echo("Empty value, not saving.", err=True)
        return

    lines: list[str] = []
    found = False

    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                line_key = stripped.split("=", 1)[0].strip()
                if line_key.upper() == key.upper():
                    lines.append(f"{key}={value}")
                    found = True
                    continue
            lines.append(line)

    if not found:
        lines.append(f"{key}={value}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    click.echo(f"Secret {key} saved to {env_path}")
