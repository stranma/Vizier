"""Agent subprocess runner: loads spec, plugin, runs agent, exits.

This module provides the entry point for agent subprocesses launched
by Pasha (Phase 4). Each invocation:
1. Loads spec from disk (fresh context)
2. Loads plugin from project config
3. Creates the appropriate agent runtime (Worker, QualityGate, or Architect)
4. Runs the agent
5. Returns the result
6. Exits (Ralph Wiggum pattern)
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from vizier.core.agent.context import AgentContext
from vizier.core.architect.runtime import ArchitectRuntime
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.model_router.router import ModelRouter
from vizier.core.models.config import ProjectConfig, ServerConfig
from vizier.core.plugins.discovery import load_plugin
from vizier.core.plugins.tool_registry import ToolRegistry
from vizier.core.quality_gate.runtime import QualityGateRuntime
from vizier.core.retrospective.runtime import RetrospectiveRuntime
from vizier.core.scout.runtime import ScoutRuntime
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.worker.runtime import WorkerRuntime

logger = logging.getLogger(__name__)


class RunResult(BaseModel):
    """Result of an agent subprocess run.

    :param agent_type: The agent type that was run (worker or quality_gate).
    :param spec_id: The spec ID that was processed.
    :param result: The outcome status string.
    :param error: Error message if the run failed.
    """

    agent_type: str
    spec_id: str
    result: str = ""
    error: str = ""


class AgentRunner:
    """Coordinates running an agent in a subprocess context.

    :param project_root: Root directory of the project.
    :param server_config: Server-wide configuration.
    :param llm_callable: LLM completion function.
    :param sentinel_llm: LLM callable for Sentinel's Haiku evaluator.
    """

    def __init__(
        self,
        project_root: str,
        server_config: ServerConfig | None = None,
        llm_callable: Any = None,
        sentinel_llm: Any = None,
    ) -> None:
        self._project_root = project_root
        self._server_config = server_config or ServerConfig()
        self._llm = llm_callable
        self._sentinel_llm = sentinel_llm

    def run_worker(self, spec_path: str, worker_id: str = "worker-0") -> RunResult:
        """Run a Worker agent on a spec.

        :param spec_path: Path to the spec file.
        :param worker_id: Identifier for this worker instance.
        :returns: RunResult with outcome.
        """
        try:
            context = AgentContext.load_from_disk(self._project_root, spec_path=spec_path)
            plugin = self._load_plugin(context)
            if plugin is None:
                return RunResult(agent_type="worker", spec_id=self._spec_id(context), error="Plugin not found")

            worker_instance = plugin.worker_class()

            sentinel = SentinelEngine(llm_callable=self._sentinel_llm)
            tool_registry = ToolRegistry(
                allowed_tools=worker_instance.allowed_tools,
                tool_restrictions=worker_instance.tool_restrictions,
                sentinel=sentinel,
            )

            project_config = ProjectConfig(**context.config) if context.config else ProjectConfig()
            router = ModelRouter(
                server_config=self._server_config,
                project_config=project_config,
                plugin_defaults=plugin.default_model_tiers,
            )

            log_path = f"reports/{context.config.get('project', 'default')}/agent-log.jsonl"
            agent_logger = AgentLogger(log_path)

            WorkerRuntime.claim_spec(spec_path, worker_id)

            context = AgentContext.load_from_disk(self._project_root, spec_path=spec_path)

            runtime = WorkerRuntime(
                context=context,
                plugin_worker=worker_instance,
                tool_registry=tool_registry,
                model_router=router,
                logger_instance=agent_logger,
                llm_callable=self._llm,
            )

            result = runtime.run()
            return RunResult(agent_type="worker", spec_id=self._spec_id(context), result=result)

        except Exception as e:
            logger.exception("Worker run failed")
            return RunResult(agent_type="worker", spec_id="unknown", error=str(e))

    def run_quality_gate(self, spec_path: str, diff: str = "") -> RunResult:
        """Run a Quality Gate agent on a spec.

        :param spec_path: Path to the spec file.
        :param diff: Git diff of the worker's changes.
        :returns: RunResult with outcome.
        """
        try:
            context = AgentContext.load_from_disk(self._project_root, spec_path=spec_path)
            plugin = self._load_plugin(context)
            if plugin is None:
                return RunResult(agent_type="quality_gate", spec_id=self._spec_id(context), error="Plugin not found")

            gate_instance = plugin.quality_gate_class()

            project_config = ProjectConfig(**context.config) if context.config else ProjectConfig()
            router = ModelRouter(
                server_config=self._server_config,
                project_config=project_config,
                plugin_defaults=plugin.default_model_tiers,
            )

            log_path = f"reports/{context.config.get('project', 'default')}/agent-log.jsonl"
            agent_logger = AgentLogger(log_path)

            runtime = QualityGateRuntime(
                context=context,
                plugin_gate=gate_instance,
                diff=diff,
                model_router=router,
                logger_instance=agent_logger,
                llm_callable=self._llm,
            )

            result = runtime.run_full_protocol()
            return RunResult(agent_type="quality_gate", spec_id=self._spec_id(context), result=result)

        except Exception as e:
            logger.exception("Quality Gate run failed")
            return RunResult(agent_type="quality_gate", spec_id="unknown", error=str(e))

    def run_architect(self, spec_path: str) -> RunResult:
        """Run an Architect agent to decompose a spec.

        :param spec_path: Path to the DRAFT or STUCK spec file.
        :returns: RunResult with outcome.
        """
        try:
            context = AgentContext.load_from_disk(self._project_root, spec_path=spec_path)
            plugin = self._load_plugin(context)
            if plugin is None:
                return RunResult(agent_type="architect", spec_id=self._spec_id(context), error="Plugin not found")

            project_config = ProjectConfig(**context.config) if context.config else ProjectConfig()
            router = ModelRouter(
                server_config=self._server_config,
                project_config=project_config,
                plugin_defaults=plugin.default_model_tiers,
            )

            log_path = f"reports/{context.config.get('project', 'default')}/agent-log.jsonl"
            agent_logger = AgentLogger(log_path)

            runtime = ArchitectRuntime(
                context=context,
                plugin=plugin,
                model_router=router,
                logger_instance=agent_logger,
                llm_callable=self._llm,
            )

            created = runtime.decompose()
            result_str = f"DECOMPOSED:{len(created)}"

            return RunResult(
                agent_type="architect",
                spec_id=self._spec_id(context),
                result=result_str,
            )

        except Exception as e:
            logger.exception("Architect run failed")
            return RunResult(agent_type="architect", spec_id="unknown", error=str(e))

    def run_scout(self, spec_path: str) -> RunResult:
        """Run a Scout agent to research prior art for a spec.

        :param spec_path: Path to the DRAFT spec file.
        :returns: RunResult with outcome.
        """
        try:
            context = AgentContext.load_from_disk(self._project_root, spec_path=spec_path)
            plugin = self._load_plugin(context)
            if plugin is None:
                return RunResult(agent_type="scout", spec_id=self._spec_id(context), error="Plugin not found")

            project_config = ProjectConfig(**context.config) if context.config else ProjectConfig()
            router = ModelRouter(
                server_config=self._server_config,
                project_config=project_config,
                plugin_defaults=plugin.default_model_tiers,
            )

            log_path = f"reports/{context.config.get('project', 'default')}/agent-log.jsonl"
            agent_logger = AgentLogger(log_path)

            runtime = ScoutRuntime(
                context=context,
                plugin=plugin,
                model_router=router,
                logger_instance=agent_logger,
                llm_callable=self._llm,
            )

            report = runtime.scout()
            return RunResult(
                agent_type="scout",
                spec_id=self._spec_id(context),
                result=f"SCOUTED:{report.decision}",
            )

        except Exception as e:
            logger.exception("Scout run failed")
            return RunResult(agent_type="scout", spec_id="unknown", error=str(e))

    def run_retrospective(self) -> RunResult:
        """Run a Retrospective agent to analyze failures and generate learnings.

        :returns: RunResult with outcome.
        """
        try:
            context = AgentContext.load_from_disk(self._project_root)

            project_config = ProjectConfig(**context.config) if context.config else ProjectConfig()
            router = ModelRouter(
                server_config=self._server_config,
                project_config=project_config,
            )

            project_name = context.config.get("project", "default")
            log_path = f"reports/{project_name}/agent-log.jsonl"
            agent_logger = AgentLogger(log_path)

            runtime = RetrospectiveRuntime(
                context=context,
                model_router=router,
                logger_instance=agent_logger,
                llm_callable=self._llm,
                agent_log_path=log_path,
            )

            result = runtime.run_analysis()
            return RunResult(
                agent_type="retrospective",
                spec_id="",
                result=result,
            )

        except Exception as e:
            logger.exception("Retrospective run failed")
            return RunResult(agent_type="retrospective", spec_id="", error=str(e))

    def _load_plugin(self, context: AgentContext) -> Any:
        plugin_name = context.config.get("plugin", "software")
        return load_plugin(plugin_name)

    @staticmethod
    def _spec_id(context: AgentContext) -> str:
        if context.spec:
            return context.spec.frontmatter.id
        return "unknown"
