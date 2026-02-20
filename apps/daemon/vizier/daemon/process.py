"""Core daemon orchestrator: Heartbeat, PingWatcher, AgentSpawner, VizierDaemon."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Heartbeat:
    """Periodic async writer to heartbeat.json. Atomic writes (tmp+rename).

    :param path: Path to the heartbeat file.
    :param interval_seconds: Seconds between heartbeat writes.
    """

    def __init__(self, path: str | Path, interval_seconds: float = 30) -> None:
        self._path = Path(path)
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._start_time = time.monotonic()
        self._cycle_count = 0
        self._active_projects: list[str] = []
        self._pid = os.getpid()

    def update(self, cycle_count: int, active_projects: list[str]) -> None:
        """Update heartbeat stats.

        :param cycle_count: Current reconciliation cycle count.
        :param active_projects: Names of currently active projects.
        """
        self._cycle_count = cycle_count
        self._active_projects = active_projects

    async def start(self) -> None:
        """Start the heartbeat background task."""
        if self._task is not None:
            return
        self._start_time = time.monotonic()
        self._task = asyncio.create_task(self._loop())
        logger.info("Heartbeat started: %s", self._path)

    async def stop(self) -> None:
        """Stop the heartbeat background task."""
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            logger.info("Heartbeat stopped")

    async def _loop(self) -> None:
        """Background loop that writes heartbeat periodically."""
        while True:
            self._write()
            await asyncio.sleep(self._interval)

    def _write(self) -> None:
        """Atomic JSON write: write to tmp file then rename."""
        from datetime import UTC, datetime

        uptime = time.monotonic() - self._start_time
        data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "pid": self._pid,
            "uptime_seconds": round(uptime, 1),
            "cycle_count": self._cycle_count,
            "active_projects": self._active_projects,
        }

        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp_path), str(self._path))


class PingWatcher:
    """Watchdog-based immediate wake-up for ping files (D50).

    Bridges watchdog thread to asyncio: when a new .json file appears
    in a ``*/pings/`` directory under specs_dir, the wakeup_event is set
    to wake the reconciliation loop immediately.

    :param specs_dir: Specs directory to watch (e.g. ``project/.vizier/specs``).
    :param wakeup_event: asyncio.Event to set when a ping is detected.
    """

    def __init__(self, specs_dir: str, wakeup_event: asyncio.Event) -> None:
        self._specs_dir = specs_dir
        self._wakeup_event = wakeup_event
        self._observer: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """Start watching for ping files."""
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer

        self._loop = asyncio.get_event_loop()

        class _PingHandler(FileSystemEventHandler):
            def __init__(inner_self) -> None:  # noqa: N805  # pyright: ignore[reportSelfClsParameterName]
                super().__init__()

            def on_created(inner_self, event: FileSystemEvent) -> None:  # noqa: N805  # pyright: ignore[reportSelfClsParameterName]
                if event.is_directory:
                    return
                path = str(event.src_path)
                if path.endswith(".json") and "/pings/" in path.replace("\\", "/"):
                    logger.debug("Ping file detected: %s", path)
                    if self._loop is not None:
                        self._loop.call_soon_threadsafe(self._wakeup_event.set)

        specs_path = Path(self._specs_dir)
        if not specs_path.is_dir():
            specs_path.mkdir(parents=True, exist_ok=True)

        observer: Any = Observer()
        observer.schedule(_PingHandler(), str(specs_path), recursive=True)
        observer.daemon = True
        observer.start()
        self._observer = observer
        logger.info("PingWatcher started: %s", self._specs_dir)

    def stop(self) -> None:
        """Stop watching for ping files."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("PingWatcher stopped")


ROLE_BUDGET_MAP: dict[str, int] = {
    "scout": 20000,
    "architect": 80000,
    "worker": 100000,
    "quality_gate": 30000,
    "retrospective": 50000,
}


class AgentSpawner:
    """Creates and runs inner-loop agents synchronously (D61).

    Called from within Pasha's thread. Each invocation creates a fresh
    AgentRuntime (Ralph Wiggum pattern).

    :param client: Anthropic client instance.
    :param sentinel: Sentinel engine for security.
    :param trace_dir: Directory for trace logs.
    """

    def __init__(self, client: Any, sentinel: Any = None, trace_dir: str = "") -> None:
        self._client = client
        self._sentinel = sentinel
        self._trace_dir = trace_dir

    def make_spawn_callback(self, project_root: str) -> Any:
        """Return a sync callable suitable as Pasha's spawn_callback.

        :param project_root: Project root directory.
        :returns: Callable(role, spec_id, context) -> dict.
        """

        def _callback(role: str, spec_id: str, context: dict[str, Any]) -> dict[str, Any]:
            return self._spawn_sync(role, spec_id, context, project_root)

        return _callback

    def _spawn_sync(self, role: str, spec_id: str, context: dict[str, Any], project_root: str) -> dict[str, Any]:
        """Dispatch to the appropriate factory, run the agent, return result.

        :param role: Agent role name.
        :param spec_id: Spec identifier.
        :param context: Additional context for the agent.
        :param project_root: Project root directory.
        :returns: Result dict with role, spec_id, stop_reason, final_text, tokens_used.
        """
        from vizier.core.runtime.budget import BudgetConfig
        from vizier.core.runtime.trace import TraceLogger

        budget_tokens = ROLE_BUDGET_MAP.get(role, 30000)
        budget = BudgetConfig(max_tokens=budget_tokens)

        trace_path = Path(self._trace_dir) / f"{role}-{spec_id}.jsonl" if self._trace_dir else None
        trace = TraceLogger(trace_path)

        try:
            runtime = self._create_runtime(role, spec_id, context, project_root, budget, trace)
        except ValueError as e:
            return {"role": role, "spec_id": spec_id, "error": str(e)}

        task_text = context.get("task", f"Execute spec {spec_id}")
        try:
            result = runtime.run(task_text)
            return {
                "role": role,
                "spec_id": spec_id,
                "stop_reason": str(result.stop_reason),
                "final_text": result.final_text[:500],
                "tokens_used": result.tokens_used,
            }
        except Exception as e:
            logger.exception("Agent %s failed on spec %s", role, spec_id)
            return {"role": role, "spec_id": spec_id, "error": str(e)}

    def _create_runtime(
        self,
        role: str,
        spec_id: str,
        context: dict[str, Any],
        project_root: str,
        budget: Any,
        trace: Any,
    ) -> Any:
        """Create an AgentRuntime for the given role.

        :param role: Agent role name.
        :param spec_id: Spec identifier.
        :param context: Additional context for the agent.
        :param project_root: Project root directory.
        :param budget: Budget configuration.
        :param trace: Trace logger.
        :returns: AgentRuntime instance.
        :raises ValueError: If role is unknown.
        """
        if role == "scout":
            from vizier.core.agents.scout.factory import create_scout_runtime

            return create_scout_runtime(
                client=self._client,
                project_root=project_root,
                spec_id=spec_id,
                sentinel=self._sentinel,
                budget=budget,
                trace=trace,
            )
        elif role == "architect":
            from vizier.core.agents.architect.factory import create_architect_runtime

            return create_architect_runtime(
                client=self._client,
                project_root=project_root,
                spec_id=spec_id,
                sentinel=self._sentinel,
                budget=budget,
                trace=trace,
            )
        elif role == "worker":
            from vizier.core.agents.worker.factory import create_worker_runtime

            return create_worker_runtime(
                client=self._client,
                project_root=project_root,
                spec_id=spec_id,
                goal=context.get("goal", ""),
                constraints=context.get("constraints", ""),
                acceptance_criteria=context.get("acceptance_criteria", ""),
                write_set_patterns=context.get("write_set_patterns"),
                complexity=context.get("complexity", "MEDIUM"),
                sentinel=self._sentinel,
                budget=budget,
                trace=trace,
            )
        elif role == "quality_gate":
            from vizier.core.agents.quality_gate.factory import create_quality_gate_runtime

            return create_quality_gate_runtime(
                client=self._client,
                project_root=project_root,
                spec_id=spec_id,
                acceptance_criteria=context.get("acceptance_criteria", ""),
                sentinel=self._sentinel,
                budget=budget,
                trace=trace,
            )
        elif role == "retrospective":
            from vizier.core.agents.retrospective.factory import create_retrospective_runtime

            return create_retrospective_runtime(
                client=self._client,
                project_root=project_root,
                sentinel=self._sentinel,
                budget=budget,
                trace=trace,
            )
        else:
            raise ValueError(f"Unknown agent role: {role}")


class VizierDaemon:
    """Main daemon orchestrator. Lifecycle: __init__ -> setup() -> run_forever()/run_once() -> shutdown().

    :param config: Daemon configuration.
    :param registry: Project registry.
    :param secret_store: Secret store for API keys.
    """

    def __init__(self, config: Any, registry: Any, secret_store: Any) -> None:
        self._config = config
        self._registry = registry
        self._secret_store = secret_store
        self._client: Any = None
        self._sentinel: Any = None
        self._ea_handler: Any = None
        self._spawner: AgentSpawner | None = None
        self._health_server: Any = None
        self._telegram: Any = None
        self._heartbeat: Heartbeat | None = None
        self._ping_watchers: list[PingWatcher] = []
        self._running = False
        self._shutdown_event: asyncio.Event | None = None
        self._wakeup_event: asyncio.Event | None = None
        self._cycle_count = 0
        self._semaphore: asyncio.Semaphore | None = None

    def setup(self) -> None:
        """Initialize all subsystems. Must be called before run_forever/run_once.

        :raises RuntimeError: If ANTHROPIC_API_KEY is not available.
        """
        from vizier.core.agents.ea.capability_summary import ProjectCapability, build_capability
        from vizier.core.agents.ea.handler import EAHandler
        from vizier.core.sentinel.engine import SentinelEngine

        from .health import HealthCheckServer

        api_key = self._secret_store.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in secret store")

        self._client = self._create_anthropic_client(api_key)
        self._sentinel = SentinelEngine()

        root = self._config.vizier_root
        trace_dir = os.path.join(root, "ea")

        capabilities: list[ProjectCapability] = []
        for project in self._registry.active_projects():
            cap = build_capability(
                name=project.name,
                plugin=project.plugin,
                local_path=project.local_path,
            )
            capabilities.append(cap)

        self._ea_handler = EAHandler(
            client=self._client,
            project_root=root,
            capabilities=capabilities,
            sentinel=self._sentinel,
            trace_dir=trace_dir,
        )

        self._spawner = AgentSpawner(self._client, self._sentinel, trace_dir)

        self._health_server = HealthCheckServer(self, port=self._config.health_check_port)

        if self._config.telegram.token:
            from .telegram import TelegramTransport

            self._telegram = TelegramTransport(
                token=self._config.telegram.token,
                ea=self._ea_handler,
                allowed_user_ids=self._config.telegram.allowed_user_ids,
            )
            self._telegram.setup()

        hb_path = os.path.join(root, self._config.heartbeat_path)
        self._heartbeat = Heartbeat(hb_path, interval_seconds=30)
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_agents)

        logger.info("VizierDaemon setup complete")

    @staticmethod
    def _create_anthropic_client(api_key: str) -> Any:
        """Create an Anthropic client. Separated for testability.

        :param api_key: Anthropic API key.
        :returns: Anthropic client instance.
        """
        import anthropic  # pyright: ignore[reportMissingImports]

        return anthropic.Anthropic(api_key=api_key)

    def get_status(self) -> dict[str, Any]:
        """Return daemon status for health check endpoint.

        :returns: Status dict with running, projects, autonomy_stage, etc.
        """
        active = self._registry.active_projects()
        return {
            "running": self._running,
            "projects": len(active),
            "project_names": [p.name for p in active],
            "autonomy_stage": self._config.autonomy.stage,
            "cycles": self._cycle_count,
            "heartbeat": self._config.heartbeat_path,
        }

    async def run_forever(self) -> None:
        """Run the daemon until shutdown signal."""
        import sys

        self._running = True
        self._shutdown_event = asyncio.Event()
        self._wakeup_event = asyncio.Event()

        if sys.platform != "win32":
            loop = asyncio.get_running_loop()
            for sig_name in ("SIGTERM", "SIGINT"):
                import signal

                sig = getattr(signal, sig_name, None)
                if sig is not None:
                    loop.add_signal_handler(sig, self._shutdown_event.set)

        if self._health_server:
            await self._health_server.start()
        if self._heartbeat:
            await self._heartbeat.start()

        for project in self._registry.active_projects():
            project_root = project.local_path or os.path.join(
                self._config.vizier_root, self._config.workspaces_dir, project.name
            )
            specs_dir = os.path.join(project_root, ".vizier", "specs")
            watcher = PingWatcher(specs_dir, self._wakeup_event)
            watcher.start()
            self._ping_watchers.append(watcher)

        tasks: list[asyncio.Task[Any]] = []
        tasks.append(asyncio.create_task(self._reconciliation_loop()))
        if self._telegram:
            tasks.append(asyncio.create_task(self._telegram.start()))

        logger.info("VizierDaemon running")

        await self._shutdown_event.wait()

        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        await self.shutdown()

    async def run_once(self) -> dict[str, Any]:
        """Run a single reconciliation pass for all active projects.

        :returns: Summary dict with per-project results.
        """
        results: dict[str, Any] = {}
        for project in self._registry.active_projects():
            result = await self._reconcile_project(project)
            results[project.name] = result
        return results

    async def shutdown(self) -> None:
        """Stop all subsystems gracefully."""
        self._running = False

        for watcher in self._ping_watchers:
            watcher.stop()
        self._ping_watchers.clear()

        if self._heartbeat:
            await self._heartbeat.stop()
        if self._health_server:
            await self._health_server.stop()
        if self._telegram:
            await self._telegram.stop()

        logger.info("VizierDaemon shutdown complete")

    async def _reconciliation_loop(self) -> None:
        """Main reconciliation loop: reconcile all projects, then sleep/wait for wake."""
        from vizier.core.watcher.adaptive import AdaptiveReconciler

        reconciler = AdaptiveReconciler()

        while self._running:
            active_names: list[str] = []
            for project in self._registry.active_projects():
                assert self._semaphore is not None
                async with self._semaphore:
                    await self._reconcile_project(project)
                active_names.append(project.name)

            self._cycle_count += 1
            if self._heartbeat:
                self._heartbeat.update(self._cycle_count, active_names)

            interval = reconciler.record_cycle(0)
            assert self._wakeup_event is not None
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wakeup_event.wait(), timeout=interval)
            self._wakeup_event.clear()

    async def _reconcile_project(self, project: Any) -> dict[str, Any]:
        """Run a reconciliation cycle for a single project.

        :param project: ProjectEntry to reconcile.
        :returns: Reconciliation result dict.
        """
        from vizier.core.agents.pasha.event_loop import PashaEventLoop

        project_root = project.local_path or os.path.join(
            self._config.vizier_root, self._config.workspaces_dir, project.name
        )

        event_loop = PashaEventLoop(project_root=project_root, plugin_name=project.plugin)
        cycle_summary = event_loop.run_reconciliation_cycle()

        ready_specs = cycle_summary.get("ready_for_assignment", [])
        pings = cycle_summary.get("pings_processed", 0)

        if not ready_specs and pings == 0:
            return {"project": project.name, "status": "idle", "cycle": cycle_summary}

        assert self._spawner is not None
        spawn_callback = self._spawner.make_spawn_callback(project_root)

        loop = asyncio.get_running_loop()
        pasha_result = await loop.run_in_executor(
            None, self._run_pasha_sync, project_root, project.name, project.plugin, cycle_summary, spawn_callback
        )

        return {"project": project.name, "status": "active", "cycle": cycle_summary, "pasha": pasha_result}

    def _run_pasha_sync(
        self,
        project_root: str,
        project_name: str,
        plugin_name: str,
        cycle_summary: dict[str, Any],
        spawn_callback: Any,
    ) -> dict[str, Any]:
        """Run Pasha synchronously in thread pool (D61).

        :param project_root: Project root directory.
        :param project_name: Project name.
        :param plugin_name: Plugin name.
        :param cycle_summary: Reconciliation cycle summary.
        :param spawn_callback: Spawn callback for inner-loop agents.
        :returns: Pasha run result dict.
        """
        from vizier.core.agents.pasha.factory import create_pasha_runtime
        from vizier.core.runtime.budget import BudgetConfig

        runtime = create_pasha_runtime(
            client=self._client,
            project_root=project_root,
            project_name=project_name,
            mode="reconciliation",
            sentinel=self._sentinel,
            spawn_callback=spawn_callback,
            budget=BudgetConfig(max_tokens=30000),
        )

        task = json.dumps(cycle_summary, indent=2)
        try:
            result = runtime.run(f"Reconciliation cycle summary:\n{task}")
            return {
                "stop_reason": str(result.stop_reason),
                "tokens_used": result.tokens_used,
                "final_text": result.final_text[:500] if result.final_text else "",
            }
        except Exception as e:
            logger.exception("Pasha runtime error for project %s", project_name)
            return {"error": str(e)}
