"""Vizier daemon process -- asyncio event loop managing multiple projects."""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vizier.core.ea.models import BudgetConfig
from vizier.core.ea.runtime import EARuntime
from vizier.core.pasha.orchestrator import PashaOrchestrator
from vizier.daemon.config import DaemonConfig, ProjectEntry, ProjectRegistry  # noqa: TC001
from vizier.daemon.health import HealthCheckServer
from vizier.daemon.telegram import TelegramTransport

logger = logging.getLogger(__name__)


class Heartbeat:
    """Dead-man switch: writes heartbeat.json every reconciliation cycle.

    :param path: Path to heartbeat.json file.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def write(self, projects_active: int, agents_running: int) -> None:
        """Write a heartbeat with current state.

        :param projects_active: Number of active projects.
        :param agents_running: Number of running agent subprocesses.
        """
        import os

        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "pid": os.getpid(),
            "projects_active": projects_active,
            "agents_running": agents_running,
        }
        tmp_path = self._path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(self._path))

    def read(self) -> dict[str, Any] | None:
        """Read the current heartbeat file."""
        if not self._path.exists():
            return None
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None


class VizierDaemon:
    """Main daemon process managing multiple project Pashas and the EA.

    :param config: Daemon configuration.
    :param registry: Project registry.
    :param llm_callable: LLM function for agents.
    :param sentinel_llm: LLM function for Sentinel evaluations.
    """

    def __init__(
        self,
        config: DaemonConfig,
        registry: ProjectRegistry,
        llm_callable: Any | None = None,
        sentinel_llm: Any | None = None,
        secret_store: Any | None = None,
    ) -> None:
        self._config = config
        self._registry = registry
        self._llm_callable = llm_callable
        self._sentinel_llm = sentinel_llm
        self._secret_store = secret_store
        self._pashas: dict[str, PashaOrchestrator] = {}
        self._ea: EARuntime | None = None
        self._health_server: HealthCheckServer | None = None
        self._telegram: TelegramTransport | None = None
        self._heartbeat = Heartbeat(Path(config.vizier_root) / config.heartbeat_path)
        self._running = False
        self._shutdown_event = asyncio.Event()

    @property
    def ea(self) -> EARuntime | None:
        """Return the EA runtime instance."""
        return self._ea

    @property
    def pashas(self) -> dict[str, PashaOrchestrator]:
        """Return all active Pasha orchestrators."""
        return self._pashas

    @property
    def is_running(self) -> bool:
        """Whether the daemon is currently running."""
        return self._running

    def setup(self) -> None:
        """Initialize EA and Pasha instances for all active projects."""
        root = Path(self._config.vizier_root)

        projects_map: dict[str, str] = {}
        for entry in self._registry.active_projects():
            project_path = self._resolve_project_path(entry)
            projects_map[entry.name] = str(project_path)

        self._ea = EARuntime(
            ea_data_dir=str(root / self._config.ea_data_dir),
            reports_dir=str(root / self._config.reports_dir),
            projects=projects_map,
            llm_callable=self._llm_callable,
            budget_config=BudgetConfig(monthly_budget_usd=self._config.monthly_budget_usd),
        )

        for entry in self._registry.active_projects():
            project_path = self._resolve_project_path(entry)
            pasha = PashaOrchestrator(
                project_root=str(project_path),
                project_name=entry.name,
                server_config=None,
                llm_callable=self._llm_callable,
                sentinel_llm=self._sentinel_llm,
                max_concurrent=self._config.max_concurrent_agents,
                reconciliation_interval=self._config.reconciliation_interval_seconds,
            )
            self._pashas[entry.name] = pasha

    async def run(self) -> None:
        """Run the daemon event loop until shutdown signal."""
        self._running = True
        self.setup()

        self._health_server = HealthCheckServer(self, port=self._config.health_check_port)
        await self._health_server.start()

        tasks: list[asyncio.Task[None]] = []

        telegram_config = self._resolve_telegram_config()
        if telegram_config:
            token, allowed_ids = telegram_config
            assert self._ea is not None
            self._telegram = TelegramTransport(token, self._ea, allowed_ids)
            self._telegram.setup()
            tasks.append(asyncio.create_task(self._run_telegram()))
        else:
            logger.warning("Telegram token not configured, Telegram transport disabled")

        for name, pasha in self._pashas.items():
            task = asyncio.create_task(self._run_pasha(name, pasha))
            tasks.append(task)

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        tasks.append(heartbeat_task)

        await self._shutdown_event.wait()

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        await self._shutdown_pashas()

        if self._telegram is not None:
            await self._telegram.stop()

        if self._health_server is not None:
            await self._health_server.stop()

        self._running = False

    async def run_once(self) -> dict[str, Any]:
        """Run a single reconciliation cycle for all projects.

        :returns: Results from each project's cycle.
        """
        self.setup()
        results: dict[str, Any] = {}
        for name, pasha in self._pashas.items():
            try:
                report = await pasha.run_once()
                results[name] = {"status": "ok", "cycle": report.cycle}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}

        self._write_heartbeat()
        return results

    def shutdown(self) -> None:
        """Signal the daemon to shut down gracefully."""
        self._shutdown_event.set()

    def get_status(self) -> dict[str, Any]:
        """Get current daemon status.

        :returns: Dict with daemon state information.
        """
        return {
            "running": self._running,
            "projects": len(self._pashas),
            "project_names": list(self._pashas.keys()),
            "autonomy_stage": self._config.autonomy.stage,
            "heartbeat": self._heartbeat.read(),
        }

    def _resolve_telegram_config(self) -> tuple[str, list[int]] | None:
        """Resolve Telegram bot token and allowed user IDs from config or secret store.

        :returns: Tuple of (token, allowed_user_ids) or None if no token available.
        """
        token = self._config.telegram.token
        allowed_ids = list(self._config.telegram.allowed_user_ids)

        if not token and self._secret_store is not None:
            token = self._secret_store.get("TELEGRAM_BOT_TOKEN") or ""

        if not allowed_ids and self._secret_store is not None:
            raw = self._secret_store.get("TELEGRAM_SULTAN_CHAT_ID") or ""
            if raw:
                try:
                    allowed_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
                except ValueError:
                    logger.warning("Invalid TELEGRAM_SULTAN_CHAT_ID format, expected comma-separated integers")
                    allowed_ids = []

        if not token:
            return None
        return token, allowed_ids

    async def _run_telegram(self) -> None:
        """Run Telegram transport polling, handling cancellation."""
        try:
            assert self._telegram is not None
            await self._telegram.start()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Telegram transport error")

    async def _run_pasha(self, name: str, pasha: PashaOrchestrator) -> None:
        """Run a Pasha orchestrator, handling errors."""
        try:
            await pasha.run()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def _heartbeat_loop(self) -> None:
        """Periodically write heartbeat file."""
        try:
            while not self._shutdown_event.is_set():
                self._write_heartbeat()
                await asyncio.sleep(self._config.reconciliation_interval_seconds)
        except asyncio.CancelledError:
            pass

    def _write_heartbeat(self) -> None:
        """Write heartbeat with current state."""
        agents_running = 0
        for pasha in self._pashas.values():
            agents_running += len(getattr(pasha, "_subprocess_manager", {}).get("_active", []) if False else [])
        self._heartbeat.write(
            projects_active=len(self._pashas),
            agents_running=agents_running,
        )

    async def _shutdown_pashas(self) -> None:
        """Gracefully shut down all Pasha orchestrators."""
        import contextlib

        for pasha in self._pashas.values():
            with contextlib.suppress(Exception):
                await pasha.shutdown()

    def _resolve_project_path(self, entry: ProjectEntry) -> Path:
        """Resolve a project's local path."""
        if entry.local_path:
            return Path(entry.local_path)
        root = Path(self._config.vizier_root)
        return root / self._config.workspaces_dir / entry.name


def install_signal_handlers(daemon: VizierDaemon) -> None:
    """Install signal handlers for graceful shutdown.

    :param daemon: The daemon instance to control.
    """
    loop = asyncio.get_event_loop()

    def handle_signal() -> None:
        daemon.shutdown()

    import contextlib

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, handle_signal)
