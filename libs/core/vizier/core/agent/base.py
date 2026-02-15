"""Base agent abstract class: fresh context, LLM call, logging."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.model_router.router import ModelRouter

if TYPE_CHECKING:
    from vizier.core.agent.context import AgentContext


class BaseAgent(ABC):
    """Abstract base class for all Vizier agents.

    Implements the fresh-context pattern: load from disk, build prompt,
    call LLM, log result, write output. Each invocation is independent.

    :param context: Immutable context loaded from disk.
    :param model_router: Router for resolving model tiers.
    :param logger: Logger for structured agent logging.
    :param llm_callable: LLM completion function (litellm.completion compatible).
    """

    def __init__(
        self,
        context: AgentContext,
        model_router: ModelRouter | None = None,
        logger: AgentLogger | None = None,
        llm_callable: Any = None,
    ) -> None:
        self._context = context
        self._router = model_router or ModelRouter()
        self._logger = logger
        self._llm = llm_callable

    @property
    def context(self) -> AgentContext:
        return self._context

    @property
    @abstractmethod
    def role(self) -> str:
        """Agent role name (e.g. 'worker', 'architect', 'quality_gate')."""
        ...

    @abstractmethod
    def build_prompt(self) -> str:
        """Build the prompt for the LLM call.

        :returns: Rendered prompt string.
        """
        ...

    @abstractmethod
    def process_response(self, response: Any) -> str:
        """Process the LLM response and write results to disk.

        :param response: The LLM completion response.
        :returns: Result status string (e.g. "REVIEW", "DONE", "REJECTED").
        """
        ...

    def resolve_model(self) -> str:
        """Resolve the concrete model for this agent's role.

        :returns: Model identifier string.
        """
        spec_complexity = None
        if self._context.spec:
            spec_complexity = self._context.spec.frontmatter.complexity
        return self._router.resolve(self.role, spec_complexity=spec_complexity)

    def run(self) -> str:
        """Execute the agent: build prompt, call LLM, process response, log.

        :returns: Result status string.
        :raises RuntimeError: If no LLM callable is configured.
        """
        if self._llm is None:
            raise RuntimeError("No LLM callable configured for agent")

        model = self.resolve_model()
        prompt = self.build_prompt()

        start_ms = _now_ms()
        response = self._llm(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        duration_ms = _now_ms() - start_ms

        result = self.process_response(response)

        if self._logger:
            spec_id = self._context.spec.frontmatter.id if self._context.spec else None
            entry = AgentLogger.entry_from_litellm_response(
                response=_response_to_dict(response),
                agent=self.role,
                model=model,
                duration_ms=duration_ms,
                project=self._context.config.get("project", ""),
                spec_id=spec_id,
                result=result,
            )
            self._logger.log(entry)

        return result


def _now_ms() -> int:
    return int(time.time() * 1000)


def _response_to_dict(response: Any) -> dict:
    if isinstance(response, dict):
        return response
    result: dict[str, Any] = {}
    if hasattr(response, "usage"):
        usage = response.usage
        result["usage"] = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
        }
    if hasattr(response, "_hidden_params"):
        result["_hidden_params"] = response._hidden_params
    return result
