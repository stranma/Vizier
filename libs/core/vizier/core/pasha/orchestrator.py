"""Pasha orchestrator: event-driven per-project agent lifecycle manager."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from vizier.core.agent_runner.runner import AgentRunner, RunResult
from vizier.core.file_protocol.spec_io import list_specs
from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.lifecycle.retry import GraduatedRetry, RetryAction
from vizier.core.lifecycle.spec_lifecycle import SpecLifecycle
from vizier.core.models.config import ServerConfig
from vizier.core.models.events import FileEvent  # noqa: TC001
from vizier.core.models.spec import Spec, SpecStatus
from vizier.core.pasha.progress import CycleReport, ProgressReporter, ProjectStatus
from vizier.core.pasha.subprocess_manager import SubprocessManager
from vizier.core.watcher.reconciler import Reconciler

logger = logging.getLogger(__name__)


class PashaOrchestrator:
    """Per-project orchestrator managing agent lifecycle.

    Owns the event-driven loop: watches for spec changes, spawns agents
    (Architect, Worker, Quality Gate), handles graduated retry, writes
    progress reports, and supports session mode for direct human interaction.

    :param project_root: Root directory of the managed project.
    :param project_name: Human-readable project name.
    :param server_config: Server-wide configuration.
    :param llm_callable: LLM completion function for agents.
    :param sentinel_llm: LLM callable for Sentinel's Haiku evaluator.
    :param max_concurrent: Maximum concurrent agent subprocesses.
    :param agent_timeout: Default timeout per agent invocation in seconds.
    :param reconciliation_interval: Seconds between reconciliation scans.
    :param state_age_threshold: Seconds a spec can stay IN_PROGRESS before warning.
    """

    def __init__(
        self,
        project_root: str | Path,
        project_name: str = "",
        server_config: ServerConfig | None = None,
        llm_callable: Any = None,
        sentinel_llm: Any = None,
        max_concurrent: int = 3,
        agent_timeout: int = 600,
        reconciliation_interval: int = 15,
        state_age_threshold: int = 1800,
    ) -> None:
        self._root = Path(project_root)
        self._name = project_name or self._root.name
        self._server_config = server_config or ServerConfig()
        self._reconciliation_interval = reconciliation_interval
        self._state_age_threshold = state_age_threshold

        self._agent_runner = AgentRunner(
            project_root=str(self._root),
            server_config=self._server_config,
            llm_callable=llm_callable,
            sentinel_llm=sentinel_llm,
        )

        self._subprocess_mgr = SubprocessManager(
            agent_runner=self._agent_runner,
            max_concurrent=max_concurrent,
            timeout_seconds=agent_timeout,
        )

        self._state_mgr = StateManager(self._root)
        self._lifecycle = SpecLifecycle()
        self._graduated_retry = GraduatedRetry()

        reports_dir = Path(self._server_config.reports_dir) / self._name
        self._progress = ProgressReporter(reports_dir)

        self._reconciler = Reconciler(self._root, self._on_event)

        self._cycle_count = 0
        self._shutdown_event: asyncio.Event | None = None
        self._running = False
        self._session_mode = False
        self._event_queue: asyncio.Queue[FileEvent] = asyncio.Queue()

        self._plugin_name = self._load_plugin_name()

    @property
    def project_name(self) -> str:
        return self._name

    @property
    def project_root(self) -> Path:
        return self._root

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_session_mode(self) -> bool:
        return self._session_mode

    @property
    def subprocess_manager(self) -> SubprocessManager:
        return self._subprocess_mgr

    @property
    def progress_reporter(self) -> ProgressReporter:
        return self._progress

    def _load_plugin_name(self) -> str:
        """Read plugin name from project config."""
        config_path = self._root / ".vizier" / "config.yaml"
        if config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data.get("plugin", "software")
            except Exception:
                pass
        return "software"

    def _on_event(self, event: FileEvent) -> None:
        """Callback for filesystem and reconciler events."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full, dropping event: %s", event.path)

    async def run(self) -> None:
        """Run the orchestration loop until shutdown.

        Alternates between processing queued events and periodic reconciliation.
        """
        self._running = True
        self._shutdown_event = asyncio.Event()

        self._lifecycle.handle_interrupted_specs(str(self._root))
        logger.info("Pasha started for project %s (plugin=%s)", self._name, self._plugin_name)

        try:
            while not self._shutdown_event.is_set():
                await self._run_cycle()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=self._reconciliation_interval,
                    )
        finally:
            self._running = False
            logger.info("Pasha stopped for project %s", self._name)

    async def run_once(self) -> CycleReport:
        """Run a single orchestration cycle (for testing).

        :returns: The cycle report for this cycle.
        """
        return await self._run_cycle()

    async def shutdown(self) -> None:
        """Gracefully shut down the orchestrator."""
        logger.info("Pasha shutting down for project %s", self._name)

        interrupted = await self._subprocess_mgr.shutdown()
        if interrupted:
            logger.info("Interrupted %d active agents", len(interrupted))

        self._lifecycle.interrupt_active_specs(str(self._root))

        if self._shutdown_event:
            self._shutdown_event.set()

        self._write_status()

    async def _run_cycle(self) -> CycleReport:
        """Execute one orchestration cycle.

        1. Reconcile disk state
        2. Process queued events
        3. Scan for actionable specs
        4. Spawn agents as needed
        5. Write progress report

        :returns: The cycle report.
        """
        self._cycle_count += 1
        specs_processed: list[str] = []
        agents_spawned: list[str] = []
        errors: list[str] = []

        self._reconciler.reconcile()

        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        tasks: list[tuple[str, str, str]] = []

        draft_specs = list_specs(str(self._root), status_filter=SpecStatus.DRAFT)
        for spec in draft_specs:
            if spec.file_path:
                tasks.append(("architect", spec.file_path, spec.frontmatter.id))

        ready_specs = list_specs(str(self._root), status_filter=SpecStatus.READY)
        for spec in sorted(ready_specs, key=lambda s: s.frontmatter.priority):
            if spec.file_path:
                tasks.append(("worker", spec.file_path, spec.frontmatter.id))

        review_specs = list_specs(str(self._root), status_filter=SpecStatus.REVIEW)
        for spec in review_specs:
            if spec.file_path:
                tasks.append(("quality_gate", spec.file_path, spec.frontmatter.id))

        rejected_specs = list_specs(str(self._root), status_filter=SpecStatus.REJECTED)
        for spec in rejected_specs:
            if spec.file_path:
                action = self._handle_rejected_spec(spec)
                specs_processed.append(spec.frontmatter.id)
                if action == RetryAction.RE_DECOMPOSE:
                    tasks.append(("architect", spec.file_path, spec.frontmatter.id))
                elif action == RetryAction.STUCK:
                    self._progress.write_escalation(
                        spec.frontmatter.id,
                        "STUCK after max retries",
                        f"Spec exhausted {spec.frontmatter.retries + 1} retries",
                    )
                elif action in (RetryAction.CONTINUE, RetryAction.BUMP_MODEL, RetryAction.ALERT_PASHA):
                    tasks.append(("worker", spec.file_path, spec.frontmatter.id))

        self._check_state_age()

        spawn_results = await asyncio.gather(
            *[self._spawn_agent(agent_type, path, spec_id) for agent_type, path, spec_id in tasks],
            return_exceptions=True,
        )

        for i, result in enumerate(spawn_results):
            agent_type, _, spec_id = tasks[i]
            if isinstance(result, Exception):
                errors.append(f"{agent_type}/{spec_id}: {result}")
            elif isinstance(result, RunResult):
                specs_processed.append(spec_id)
                agents_spawned.append(f"{agent_type}:{spec_id}")
                if result.error:
                    errors.append(f"{agent_type}/{spec_id}: {result.error}")

        report = CycleReport(
            cycle=self._cycle_count,
            timestamp=datetime.utcnow().isoformat(),
            specs_processed=specs_processed,
            agents_spawned=agents_spawned,
            errors=errors,
        )
        self._progress.write_cycle_report(report)
        self._write_status()

        return report

    async def _spawn_agent(self, agent_type: str, spec_path: str, spec_id: str) -> RunResult:
        """Spawn an agent via the subprocess manager.

        :param agent_type: Type of agent (architect, worker, quality_gate).
        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier.
        :returns: RunResult from the agent.
        """
        logger.info("Spawning %s for spec %s", agent_type, spec_id)

        if agent_type == "architect":
            return await self._subprocess_mgr.spawn_architect(spec_path, spec_id)
        if agent_type == "worker":
            return await self._subprocess_mgr.spawn_worker(spec_path, spec_id)
        if agent_type == "quality_gate":
            return await self._subprocess_mgr.spawn_quality_gate(spec_path, spec_id)

        return RunResult(agent_type=agent_type, spec_id=spec_id, error=f"Unknown agent type: {agent_type}")

    def _handle_rejected_spec(self, spec: Spec) -> RetryAction:
        """Process a REJECTED spec through graduated retry logic.

        :param spec: The rejected spec.
        :returns: The retry action taken.
        """
        if not spec.file_path:
            return RetryAction.CONTINUE

        try:
            action = self._lifecycle.handle_rejection(spec.file_path)
            logger.info(
                "Rejected spec %s: retry %d, action=%s",
                spec.frontmatter.id,
                spec.frontmatter.retries + 1,
                action.value,
            )
            return action
        except Exception as e:
            logger.exception("Failed to handle rejection for spec %s: %s", spec.frontmatter.id, e)
            return RetryAction.CONTINUE

    def _check_state_age(self) -> None:
        """Check for specs stuck in IN_PROGRESS beyond threshold."""
        in_progress = list_specs(str(self._root), status_filter=SpecStatus.IN_PROGRESS)
        now = datetime.utcnow()

        for spec in in_progress:
            updated = spec.frontmatter.updated
            age_seconds = (now - updated).total_seconds()

            if age_seconds > self._state_age_threshold:
                is_active = spec.frontmatter.id in {p.spec_id for p in self._subprocess_mgr.active_processes}
                if not is_active:
                    logger.warning(
                        "Spec %s stuck IN_PROGRESS for %.0fs with no active agent",
                        spec.frontmatter.id,
                        age_seconds,
                    )
                    self._progress.write_escalation(
                        spec.frontmatter.id,
                        "Stuck IN_PROGRESS",
                        f"In state for {age_seconds:.0f}s with no active agent subprocess",
                    )

    def _write_status(self) -> None:
        """Write current project status to reports directory."""
        all_specs = list_specs(str(self._root))
        by_status: dict[str, int] = {}
        for spec in all_specs:
            status = spec.frontmatter.status.value
            by_status[status] = by_status.get(status, 0) + 1

        status = ProjectStatus(
            project=self._name,
            timestamp=datetime.utcnow().isoformat(),
            total_specs=len(all_specs),
            by_status=by_status,
            active_agents=self._subprocess_mgr.active_count,
            cycle_count=self._cycle_count,
        )
        self._progress.write_status(status)

    def enter_session(self) -> None:
        """Enter session mode for direct human interaction."""
        self._session_mode = True
        logger.info("Pasha entering session mode for project %s", self._name)

    def exit_session(self, summary: str = "") -> str:
        """Exit session mode and write session summary.

        :param summary: Session summary text.
        :returns: Path to the written summary file (or empty string).
        """
        self._session_mode = False
        logger.info("Pasha exiting session mode for project %s", self._name)

        if summary:
            return self._write_session_summary(summary)
        return ""

    def _write_session_summary(self, summary: str) -> str:
        """Write session summary for EA to read.

        :param summary: Summary text.
        :returns: Path to the written file.
        """
        import os

        sessions_dir = Path("ea") / "sessions"
        sessions_dir.mkdir(parents=True, exist_ok=True)

        date = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"{date}-{self._name}.md"
        path = sessions_dir / filename

        content = f"# Session Summary: {self._name}\n\n**Date:** {date}\n\n## Summary\n\n{summary}\n"
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(str(tmp), str(path))

        return str(path)
