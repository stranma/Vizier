"""CLI commands for daemon management: init, register, start, stop, status."""

from __future__ import annotations

import json
import os
import signal
from pathlib import Path

import click

from vizier.daemon.config import (
    DaemonConfig,
    ProjectEntry,
    ProjectRegistry,
    load_daemon_config,
    load_project_registry,
    save_project_registry,
)


def _default_root() -> str:
    return os.environ.get("VIZIER_ROOT", "/opt/vizier")


def _config_path(root: str) -> Path:
    return Path(root) / "config.yaml"


def _registry_path(root: str) -> Path:
    return Path(root) / "projects.yaml"


def _pid_path(root: str) -> Path:
    return Path(root) / "vizier.pid"


@click.command("init")
@click.option("--root", default=None, help="Vizier root directory (default: /opt/vizier or $VIZIER_ROOT).")
def daemon_init(root: str | None) -> None:
    """Initialize the Vizier directory structure."""
    vizier_root = root or _default_root()
    root_path = Path(vizier_root)

    dirs = ["workspaces", "reports", "ea", "security", "checkout", "logs"]
    created = []
    for d in dirs:
        dir_path = root_path / d
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(d)

    config_file = _config_path(vizier_root)
    if not config_file.exists():
        config = DaemonConfig(vizier_root=vizier_root)
        import yaml

        config_file.write_text(
            yaml.dump(config.model_dump(mode="json"), default_flow_style=False),
            encoding="utf-8",
        )
        click.echo(f"Created config: {config_file}")

    registry_file = _registry_path(vizier_root)
    if not registry_file.exists():
        save_project_registry(ProjectRegistry(), registry_file)
        click.echo(f"Created registry: {registry_file}")

    if created:
        click.echo(f"Created directories: {', '.join(created)}")
    click.echo(f"Vizier initialized at {vizier_root}")


@click.command("register")
@click.argument("name")
@click.option("--repo", default="", help="Git repository URL.")
@click.option("--local-path", default="", help="Local path to project (overrides clone).")
@click.option("--plugin", default="software", help="Plugin to use (software, documents).")
@click.option("--root", default=None, help="Vizier root directory.")
def daemon_register(name: str, repo: str, local_path: str, plugin: str, root: str | None) -> None:
    """Register a project with Vizier."""
    vizier_root = root or _default_root()
    registry_file = _registry_path(vizier_root)
    registry = load_project_registry(registry_file)

    entry = ProjectEntry(
        name=name,
        repo_url=repo,
        local_path=local_path,
        plugin=plugin,
    )

    try:
        registry.add(entry)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1) from None

    save_project_registry(registry, registry_file)
    click.echo(f"Registered project: {name}")
    if repo:
        click.echo(f"  Repository: {repo}")
    if local_path:
        click.echo(f"  Local path: {local_path}")
    click.echo(f"  Plugin: {plugin}")


@click.command("start")
@click.option("--root", default=None, help="Vizier root directory.")
@click.option("--once", is_flag=True, help="Run a single reconciliation cycle and exit.")
def daemon_start(root: str | None, once: bool) -> None:
    """Start the Vizier daemon."""
    import asyncio

    vizier_root = root or _default_root()
    config = load_daemon_config(_config_path(vizier_root))
    config = config.model_copy(update={"vizier_root": vizier_root})
    registry = load_project_registry(_registry_path(vizier_root))

    if not registry.active_projects():
        click.echo("No active projects registered. Use 'vizier register' first.", err=True)
        raise SystemExit(1)

    from vizier.core.llm.factory import create_llm_callable
    from vizier.core.secrets.startup import create_secret_store, load_bootstrap_credentials, sanitize_environment
    from vizier.daemon.process import VizierDaemon, install_signal_handlers

    bootstrap = load_bootstrap_credentials(vizier_root)
    store = create_secret_store(
        vizier_root,
        azure_vault_url=config.azure_vault_url,
        azure_tenant_id=bootstrap["azure_tenant_id"],
        azure_client_id=bootstrap["azure_client_id"],
        azure_client_secret=bootstrap["azure_client_secret"],
    )

    llm_callable = None
    sentinel_llm = None
    try:
        llm_callable = create_llm_callable(store)
        sentinel_llm = create_llm_callable(store)
        click.echo("  LLM: configured")
    except Exception as e:
        click.echo(f"  LLM: not configured ({e})", err=True)

    sanitize_environment(store.keys())

    daemon = VizierDaemon(config, registry, llm_callable=llm_callable, sentinel_llm=sentinel_llm, secret_store=store)

    if once:
        click.echo(f"Running single cycle for {len(registry.active_projects())} project(s)...")
        results = asyncio.run(daemon.run_once())
        for name, result in results.items():
            status = result.get("status", "unknown")
            click.echo(f"  {name}: {status}")
        return

    pid_file = _pid_path(vizier_root)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")

    click.echo(f"Starting Vizier daemon (PID {os.getpid()})...")
    click.echo(f"  Projects: {len(registry.active_projects())}")
    click.echo(f"  Max concurrent agents: {config.max_concurrent_agents}")
    click.echo(f"  Autonomy stage: {config.autonomy.stage}")
    click.echo(f"  Health check: http://0.0.0.0:{config.health_check_port}/health")
    telegram_status = "configured" if config.telegram.token else "not configured"
    click.echo(f"  Telegram: {telegram_status}")

    import contextlib

    with contextlib.suppress(NotImplementedError):
        install_signal_handlers(daemon)

    try:
        asyncio.run(daemon.run())
    finally:
        if pid_file.exists():
            pid_file.unlink()

    click.echo("Daemon stopped.")


@click.command("stop")
@click.option("--root", default=None, help="Vizier root directory.")
def daemon_stop(root: str | None) -> None:
    """Stop the Vizier daemon."""
    vizier_root = root or _default_root()
    pid_file = _pid_path(vizier_root)

    if not pid_file.exists():
        click.echo("No running daemon found (no PID file).", err=True)
        raise SystemExit(1)

    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError) as e:
        click.echo(f"Error reading PID file: {e}", err=True)
        raise SystemExit(1) from None

    try:
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent SIGTERM to daemon (PID {pid})")
    except (ProcessLookupError, OSError):
        click.echo(f"Daemon process {pid} not found. Cleaning up PID file.")
        pid_file.unlink(missing_ok=True)


@click.command("status")
@click.option("--root", default=None, help="Vizier root directory.")
def daemon_status(root: str | None) -> None:
    """Show Vizier daemon and project status."""
    vizier_root = root or _default_root()
    root_path = Path(vizier_root)

    if not root_path.exists():
        click.echo(f"Vizier root not found: {vizier_root}", err=True)
        click.echo("Run 'vizier init' first.", err=True)
        raise SystemExit(1)

    registry = load_project_registry(_registry_path(vizier_root))
    config = load_daemon_config(_config_path(vizier_root))

    pid_file = _pid_path(vizier_root)
    daemon_running = False
    daemon_pid = None
    if pid_file.exists():
        try:
            daemon_pid = int(pid_file.read_text(encoding="utf-8").strip())
            os.kill(daemon_pid, 0)
            daemon_running = True
        except (ValueError, OSError):
            daemon_running = False

    import contextlib

    hb_path = root_path / config.heartbeat_path
    heartbeat = None
    if hb_path.exists():
        with contextlib.suppress(json.JSONDecodeError, OSError):
            heartbeat = json.loads(hb_path.read_text(encoding="utf-8"))

    click.echo("Vizier Status")
    click.echo(f"  Root: {vizier_root}")
    click.echo(
        f"  Daemon: {'running' if daemon_running else 'stopped'}" + (f" (PID {daemon_pid})" if daemon_pid else "")
    )
    click.echo(f"  Autonomy stage: {config.autonomy.stage}")

    if heartbeat:
        click.echo(f"  Last heartbeat: {heartbeat.get('timestamp', 'unknown')}")

    click.echo(f"\nProjects ({len(registry.projects)}):")
    if not registry.projects:
        click.echo("  (none registered)")
    else:
        for p in registry.projects:
            status_str = "active" if p.active else "inactive"
            click.echo(f"  {p.name} [{status_str}] plugin={p.plugin}")
            if p.repo_url:
                click.echo(f"    repo: {p.repo_url}")
            if p.local_path:
                click.echo(f"    path: {p.local_path}")
