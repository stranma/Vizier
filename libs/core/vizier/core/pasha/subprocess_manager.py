"""Agent subprocess manager: spawn, track, timeout, and kill agent processes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from vizier.core.agent_runner.runner import AgentRunner, RunResult

logger = logging.getLogger(__name__)


class AgentProcess(BaseModel):
    """Tracks a running or completed agent subprocess.

    :param agent_type: Type of agent (worker, quality_gate, architect).
    :param spec_id: The spec ID being processed.
    :param spec_path: Path to the spec file.
    :param started_at: When the agent was launched.
    :param result: Result once completed (None while running).
    :param error: Error message if failed.
    :param timed_out: Whether the agent was killed due to timeout.
    """

    agent_type: str
    spec_id: str
    spec_path: str
    started_at: str = ""
    result: RunResult | None = None
    error: str = ""
    timed_out: bool = False


class SubprocessManager:
    """Manages agent subprocess lifecycle with concurrency limiting.

    Uses asyncio to run agents concurrently up to max_concurrent limit.
    Agents are run via AgentRunner in thread pool to avoid blocking.

    :param agent_runner: The AgentRunner instance for running agents.
    :param max_concurrent: Maximum number of concurrent agent subprocesses.
    :param timeout_seconds: Default timeout per agent invocation.
    """

    def __init__(
        self,
        agent_runner: AgentRunner,
        max_concurrent: int = 3,
        timeout_seconds: int = 600,
    ) -> None:
        self._runner = agent_runner
        self._max_concurrent = max_concurrent
        self._timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active: dict[str, AgentProcess] = {}
        self._completed: list[AgentProcess] = []
        self._shutdown = False

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_processes(self) -> list[AgentProcess]:
        return list(self._active.values())

    @property
    def completed_processes(self) -> list[AgentProcess]:
        return list(self._completed)

    async def spawn_worker(self, spec_path: str, spec_id: str, worker_id: str = "worker-0") -> RunResult:
        """Spawn a Worker agent with concurrency limiting and timeout.

        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier for tracking.
        :param worker_id: Worker instance identifier.
        :returns: RunResult from the agent.
        """
        return await self._spawn("worker", spec_path, spec_id, worker_id=worker_id)

    async def spawn_quality_gate(self, spec_path: str, spec_id: str, diff: str = "") -> RunResult:
        """Spawn a Quality Gate agent with concurrency limiting and timeout.

        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier for tracking.
        :param diff: Git diff for the quality gate.
        :returns: RunResult from the agent.
        """
        return await self._spawn("quality_gate", spec_path, spec_id, diff=diff)

    async def spawn_scout(self, spec_path: str, spec_id: str) -> RunResult:
        """Spawn a Scout agent with concurrency limiting and timeout.

        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier for tracking.
        :returns: RunResult from the agent.
        """
        return await self._spawn("scout", spec_path, spec_id)

    async def spawn_architect(self, spec_path: str, spec_id: str) -> RunResult:
        """Spawn an Architect agent with concurrency limiting and timeout.

        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier for tracking.
        :returns: RunResult from the agent.
        """
        return await self._spawn("architect", spec_path, spec_id)

    async def _spawn(self, agent_type: str, spec_path: str, spec_id: str, **kwargs: Any) -> RunResult:
        """Internal spawn method with semaphore and timeout.

        :param agent_type: Type of agent to spawn.
        :param spec_path: Path to the spec file.
        :param spec_id: Spec identifier.
        :returns: RunResult from the agent.
        """
        if self._shutdown:
            return RunResult(agent_type=agent_type, spec_id=spec_id, error="Orchestrator shutting down")

        process = AgentProcess(agent_type=agent_type, spec_id=spec_id, spec_path=spec_path)

        async with self._semaphore:
            self._active[spec_id] = process
            try:
                result = await asyncio.wait_for(
                    self._run_in_thread(agent_type, spec_path, spec_id, **kwargs),
                    timeout=self._timeout,
                )
                process.result = result
                return result

            except TimeoutError:
                logger.warning("Agent %s for spec %s timed out after %ds", agent_type, spec_id, self._timeout)
                process.timed_out = True
                process.error = f"Timeout after {self._timeout}s"
                return RunResult(
                    agent_type=agent_type,
                    spec_id=spec_id,
                    error=f"Timeout after {self._timeout}s",
                )

            except Exception as e:
                logger.exception("Agent %s for spec %s crashed", agent_type, spec_id)
                process.error = str(e)
                return RunResult(agent_type=agent_type, spec_id=spec_id, error=str(e))

            finally:
                self._active.pop(spec_id, None)
                self._completed.append(process)

    async def _run_in_thread(self, agent_type: str, spec_path: str, spec_id: str, **kwargs: Any) -> RunResult:
        """Run agent in a thread pool to avoid blocking the event loop.

        :param agent_type: Type of agent to run.
        :param spec_path: Path to spec file.
        :param spec_id: Spec identifier.
        :returns: RunResult from the agent.
        """
        loop = asyncio.get_event_loop()
        if agent_type == "worker":
            return await loop.run_in_executor(
                None, lambda: self._runner.run_worker(spec_path, worker_id=kwargs.get("worker_id", "worker-0"))
            )
        if agent_type == "quality_gate":
            return await loop.run_in_executor(
                None, lambda: self._runner.run_quality_gate(spec_path, diff=kwargs.get("diff", ""))
            )
        if agent_type == "architect":
            return await loop.run_in_executor(None, lambda: self._runner.run_architect(spec_path))
        if agent_type == "scout":
            return await loop.run_in_executor(None, lambda: self._runner.run_scout(spec_path))

        return RunResult(agent_type=agent_type, spec_id=spec_id, error=f"Unknown agent type: {agent_type}")

    async def shutdown(self) -> list[str]:
        """Graceful shutdown: mark active specs as needing interruption.

        :returns: List of spec IDs that were active at shutdown.
        """
        self._shutdown = True
        interrupted = list(self._active.keys())
        logger.info("Subprocess manager shutting down, %d active agents", len(interrupted))
        return interrupted
