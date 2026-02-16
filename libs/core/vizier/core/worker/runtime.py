"""Worker agent runtime: fresh-context executor for a single spec."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from vizier.core.agent.base import BaseAgent
from vizier.core.file_protocol.spec_io import list_specs, update_spec_status
from vizier.core.models.spec import SpecStatus

if TYPE_CHECKING:
    from vizier.core.agent.context import AgentContext
    from vizier.core.logging.agent_logger import AgentLogger
    from vizier.core.model_router.router import ModelRouter
    from vizier.core.plugins.base_worker import BaseWorker
    from vizier.core.plugins.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class WorkerRuntime(BaseAgent):
    """Worker agent: picks a READY spec, calls plugin worker, writes results.

    Implements the Ralph Wiggum pattern: fresh context, one spec, exit.
    Completion is implicit -- clean exit transitions spec to REVIEW.

    :param context: Agent context loaded from disk.
    :param plugin_worker: Plugin-provided worker instance.
    :param tool_registry: Tool registry for sandbox enforcement.
    :param model_router: Model router for tier resolution.
    :param logger_instance: Agent logger for structured logging.
    :param llm_callable: LLM completion function.
    """

    def __init__(
        self,
        context: AgentContext,
        plugin_worker: BaseWorker,
        tool_registry: ToolRegistry | None = None,
        model_router: ModelRouter | None = None,
        logger_instance: AgentLogger | None = None,
        llm_callable: Any = None,
    ) -> None:
        super().__init__(
            context=context,
            model_router=model_router,
            logger=logger_instance,
            llm_callable=llm_callable,
        )
        self._plugin_worker = plugin_worker
        self._tool_registry = tool_registry
        self._exploration_log: list[str] = []

    @property
    def role(self) -> str:
        return "worker"

    @property
    def plugin_worker(self) -> BaseWorker:
        return self._plugin_worker

    @property
    def exploration_log(self) -> list[str]:
        """Files read beyond the artifact list (for Retrospective analysis)."""
        return list(self._exploration_log)

    def log_exploration_read(self, file_path: str) -> None:
        """Record a read-only exploration beyond the artifact list.

        :param file_path: Path to the file that was read.
        """
        if file_path not in self._exploration_log:
            self._exploration_log.append(file_path)
            logger.info("Worker explored beyond artifact list: %s", file_path)

    def build_prompt(self) -> str:
        """Build prompt using the plugin worker's template.

        :returns: Rendered prompt string.
        """
        if self._context.spec is None:
            raise RuntimeError("Worker requires a spec in context")

        return self._plugin_worker.get_prompt(
            self._context.spec,
            self._context.as_dict(),
        )

    def process_response(self, response: Any) -> str:
        """Process LLM response. Clean exit -> REVIEW transition.

        :param response: LLM completion response.
        :returns: Result status string.
        """
        if self._context.spec is None:
            raise RuntimeError("Worker requires a spec in context")

        spec_path = self._context.spec.file_path
        if spec_path is None:
            raise RuntimeError("Spec has no file_path")

        update_spec_status(spec_path, SpecStatus.REVIEW)

        return SpecStatus.REVIEW.value

    @staticmethod
    def pick_next_spec(project_root: str) -> str | None:
        """Pick the highest-priority READY spec.

        :param project_root: Root directory of the project.
        :returns: File path of the spec to work on, or None if no READY specs.
        """
        ready_specs = list_specs(project_root, status_filter=SpecStatus.READY)
        if not ready_specs:
            return None

        ready_specs.sort(key=lambda s: s.frontmatter.priority)
        return ready_specs[0].file_path

    @staticmethod
    def claim_spec(spec_path: str, worker_id: str) -> None:
        """Transition spec from READY to IN_PROGRESS and assign to this worker.

        :param spec_path: Path to the spec file.
        :param worker_id: Identifier for this worker instance.
        """
        update_spec_status(
            spec_path,
            SpecStatus.IN_PROGRESS,
            extra_updates={"assigned_to": worker_id},
        )
