"""Core daemon orchestrator: Heartbeat, PingWatcher, AgentSpawner, VizierDaemon."""

from __future__ import annotations

import asyncio
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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
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
            def __init__(inner_self) -> None:  # noqa: N805
                super().__init__()

            def on_created(inner_self, event: FileSystemEvent) -> None:  # noqa: N805
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

    def _spawn_sync(
        self, role: str, spec_id: str, context: dict[str, Any], project_root: str
    ) -> dict[str, Any]:
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
