"""EA message handler: bridges TelegramTransport and AgentRuntime.

Provides the handle_message(text) -> str interface expected by
TelegramTransport. Creates a fresh AgentRuntime per invocation
with JIT prompt assembly (D42).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vizier.core.agents.ea.capability_summary import (
    ProjectCapability,
    format_capabilities_for_prompt,
)
from vizier.core.agents.ea.factory import create_ea_runtime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger
from vizier.core.runtime.types import StopReason

if TYPE_CHECKING:
    from collections.abc import Callable

    from vizier.core.sentinel.engine import SentinelEngine

logger = logging.getLogger(__name__)


class EAHandler:
    """Bridges Telegram/CLI transport with EA AgentRuntime.

    Each handle_message() call creates a fresh AgentRuntime with
    JIT-assembled prompt based on message classification.

    :param client: Anthropic client (or mock).
    :param project_root: Root directory for file/spec operations.
    :param model: Model identifier for the EA.
    :param capabilities: Project capability summaries.
    :param priorities: Sultan's current priorities text.
    :param sentinel: Optional Sentinel engine.
    :param budget: Budget config per invocation.
    :param trace_dir: Directory for trace logs.
    :param send_callback: Telegram delivery callback for briefings.
    """

    def __init__(
        self,
        *,
        client: Any,
        project_root: str = "",
        model: str = "",
        capabilities: list[ProjectCapability] | None = None,
        priorities: str = "",
        sentinel: SentinelEngine | None = None,
        budget: BudgetConfig | None = None,
        trace_dir: str = "",
        send_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._client = client
        self._project_root = project_root
        self._model = model or "claude-opus-4-20250514"
        self._capabilities = capabilities or []
        self._priorities = priorities
        self._sentinel = sentinel
        self._budget = budget or BudgetConfig(max_tokens=50000)
        self._trace_dir = trace_dir
        self._send_callback = send_callback

    def handle_message(self, text: str) -> str:
        """Handle an incoming message from Sultan.

        Creates a fresh AgentRuntime with JIT-assembled prompt,
        runs the agent loop, and returns the response.

        :param text: Incoming message text.
        :returns: EA's response text.
        """
        trace_path = Path(self._trace_dir) / "ea-trace.jsonl" if self._trace_dir else None
        trace = TraceLogger(trace_path)

        runtime = create_ea_runtime(
            client=self._client,
            project_root=self._project_root,
            model=self._model,
            capabilities=self._capabilities,
            priorities=self._priorities,
            sentinel=self._sentinel,
            budget=self._budget,
            trace=trace,
            send_callback=self._send_callback,
            initial_message=text,
        )

        try:
            result = runtime.run(text)
            if result.stop_reason == StopReason.ERROR:
                error_detail = result.error or "Unknown error"
                logger.error("EA runtime error: %s", error_detail)
                return f"An error occurred: {error_detail}"
            return result.final_text or "I processed your request but have no text response."
        except Exception:
            logger.exception("EA runtime error")
            return "An error occurred while processing your request."

    def update_capabilities(self, capabilities: list[ProjectCapability]) -> None:
        """Update the project capability summaries.

        :param capabilities: New list of project capabilities.
        """
        self._capabilities = capabilities

    def update_priorities(self, priorities: str) -> None:
        """Update Sultan's priorities text.

        :param priorities: New priorities text.
        """
        self._priorities = priorities

    @property
    def capabilities_text(self) -> str:
        """Return formatted capabilities for debugging."""
        return format_capabilities_for_prompt(self._capabilities)
