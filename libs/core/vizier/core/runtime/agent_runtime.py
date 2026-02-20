"""AgentRuntime: wraps Anthropic client with Sentinel hook, budget, trace (D47)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from vizier.core.runtime.budget import BudgetConfig, BudgetTracker
from vizier.core.runtime.loop_guardian import GuardianConfig, GuardianVerdict, LoopGuardian
from vizier.core.runtime.trace import TraceLogger
from vizier.core.runtime.types import RunResult, StopReason, ToolCallRecord, ToolDefinition
from vizier.core.sentinel.engine import SentinelEngine  # noqa: TC001
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Agent execution runtime with Sentinel, budget, Loop Guardian, and trace.

    Wraps the Anthropic messages.create API in an agentic tool loop.
    Each call to run() starts fresh (no conversation history carried between runs).

    :param client: An object with a .messages.create() method (Anthropic client or mock).
    :param model: Model identifier string (e.g. "claude-sonnet-4-6").
    :param system_prompt: System prompt for the agent.
    :param tools: List of tool definitions available to the agent.
    :param sentinel: Optional Sentinel engine for tool call security.
    :param budget: Optional budget configuration.
    :param guardian: Optional Loop Guardian configuration (D51).
    :param guardian_llm_checkpoint: Optional LLM callable for guardian checkpoints.
    :param trace: Optional trace logger for Golden Trace.
    :param agent_role: Agent role name for Sentinel and logging.
    :param spec_id: Spec ID for context.
    """

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        system_prompt: str,
        tools: list[ToolDefinition] | None = None,
        sentinel: SentinelEngine | None = None,
        budget: BudgetConfig | None = None,
        guardian: GuardianConfig | None = None,
        guardian_llm_checkpoint: Any | None = None,
        trace: TraceLogger | None = None,
        agent_role: str = "",
        spec_id: str = "",
    ) -> None:
        self._client = client
        self._model = model
        self._system_prompt = system_prompt
        self._tools = {t.name: t for t in (tools or [])}
        self._sentinel = sentinel
        self._budget = BudgetTracker(budget)
        self._guardian = LoopGuardian(guardian, guardian_llm_checkpoint)
        self._trace = trace or TraceLogger()
        self._agent_role = agent_role
        self._spec_id = spec_id

    @property
    def budget(self) -> BudgetTracker:
        """Access the budget tracker."""
        return self._budget

    @property
    def guardian(self) -> LoopGuardian:
        """Access the Loop Guardian."""
        return self._guardian

    @property
    def trace(self) -> TraceLogger:
        """Access the trace logger."""
        return self._trace

    def run(self, task: str, *, max_tokens_per_turn: int = 4096) -> RunResult:
        """Execute the agent loop until completion or budget exhaustion.

        :param task: The user message / task description.
        :param max_tokens_per_turn: Max tokens per API call.
        :returns: RunResult with final output and metadata.
        """
        self._budget.reset()
        self._guardian.reset()
        tool_calls: list[ToolCallRecord] = []

        self._trace.log(
            "run_start",
            {
                "agent_role": self._agent_role,
                "spec_id": self._spec_id,
                "model": self._model,
                "task": task[:500],
            },
        )

        api_tools = self._build_api_tools()
        messages: list[dict[str, Any]] = [{"role": "user", "content": task}]

        while True:
            if self._budget.is_exhausted():
                self._trace.log(
                    "budget_exhausted",
                    {
                        "tokens_used": self._budget.tokens_used,
                        "turns": self._budget.turns,
                    },
                )
                return RunResult(
                    stop_reason=StopReason.BUDGET_EXHAUSTED,
                    tool_calls=tool_calls,
                    tokens_used=self._budget.tokens_used,
                    turns=self._budget.turns,
                )

            try:
                response = self._call_api(messages, api_tools, max_tokens_per_turn)
            except Exception as e:
                self._trace.log("api_error", {"error": str(e)})
                return RunResult(
                    stop_reason=StopReason.ERROR,
                    error=str(e),
                    tool_calls=tool_calls,
                    tokens_used=self._budget.tokens_used,
                    turns=self._budget.turns,
                )

            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)
            self._budget.record_usage(input_tokens, output_tokens)

            stop_reason = getattr(response, "stop_reason", "end_turn")

            if stop_reason == "end_turn":
                final_text = self._extract_text(response)
                self._trace.log(
                    "run_complete",
                    {
                        "final_text": final_text[:500],
                        "tokens_used": self._budget.tokens_used,
                        "turns": self._budget.turns,
                    },
                )
                return RunResult(
                    stop_reason=StopReason.COMPLETED,
                    final_text=final_text,
                    tool_calls=tool_calls,
                    tokens_used=self._budget.tokens_used,
                    turns=self._budget.turns,
                )

            if stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": self._serialize_content(response)})

                tool_results = []
                halted = False
                for block in response.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue

                    record = self._execute_tool(block.name, block.input)
                    tool_calls.append(record)

                    # Loop Guardian check after each tool call
                    success = record.sentinel_decision != "DENY" and "error" not in str(record.tool_result)
                    verdict = self._guardian.record_call(
                        tool_name=record.tool_name,
                        tool_input=record.tool_input,
                        success=success,
                        result_preview=str(record.tool_result)[:200],
                    )
                    if verdict == GuardianVerdict.HALT:
                        self._trace.log(
                            "guardian_halt",
                            {
                                "tool": record.tool_name,
                                "total_calls": self._guardian.total_calls,
                            },
                        )
                        halted = True

                    if record.sentinel_decision == "DENY":
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({"error": "Permission denied by Sentinel"}),
                                "is_error": True,
                            }
                        )
                    else:
                        result_str = (
                            json.dumps(record.tool_result, default=str)
                            if not isinstance(record.tool_result, str)
                            else record.tool_result
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str,
                            }
                        )

                if halted:
                    return RunResult(
                        stop_reason=StopReason.ERROR,
                        error="Loop Guardian halted: agent spinning detected",
                        tool_calls=tool_calls,
                        tokens_used=self._budget.tokens_used,
                        turns=self._budget.turns,
                    )

                messages.append({"role": "user", "content": tool_results})
                continue

            final_text = self._extract_text(response)
            return RunResult(
                stop_reason=StopReason.COMPLETED,
                final_text=final_text,
                tool_calls=tool_calls,
                tokens_used=self._budget.tokens_used,
                turns=self._budget.turns,
            )

    def _call_api(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> Any:
        """Call the Anthropic messages.create API."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": self._system_prompt,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return self._client.messages.create(**kwargs)

    def _execute_tool(self, name: str, input_data: dict[str, Any]) -> ToolCallRecord:
        """Execute a single tool call with Sentinel check."""
        start = time.monotonic()

        if self._sentinel is not None:
            request = ToolCallRequest(
                tool=name,
                args=input_data,
                agent_role=self._agent_role,
                spec_id=self._spec_id,
            )
            sentinel_result = self._sentinel.evaluate(request)

            if sentinel_result.decision == PolicyDecision.DENY:
                self._trace.log(
                    "tool_blocked",
                    {
                        "tool": name,
                        "reason": sentinel_result.reason,
                    },
                )
                return ToolCallRecord(
                    tool_name=name,
                    tool_input=input_data,
                    tool_result={"error": f"Blocked by Sentinel: {sentinel_result.reason}"},
                    sentinel_decision="DENY",
                )

        tool_def = self._tools.get(name)
        if tool_def is None:
            self._trace.log("tool_not_found", {"tool": name})
            return ToolCallRecord(
                tool_name=name,
                tool_input=input_data,
                tool_result={"error": f"Unknown tool: {name}"},
                sentinel_decision="ALLOW",
            )

        try:
            result = tool_def.handler(**input_data)
            duration = int((time.monotonic() - start) * 1000)

            self._trace.log(
                "tool_call",
                {
                    "tool": name,
                    "duration_ms": duration,
                },
            )

            return ToolCallRecord(
                tool_name=name,
                tool_input=input_data,
                tool_result=result,
                sentinel_decision="ALLOW",
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            self._trace.log(
                "tool_error",
                {
                    "tool": name,
                    "error": str(e),
                    "duration_ms": duration,
                },
            )
            return ToolCallRecord(
                tool_name=name,
                tool_input=input_data,
                tool_result={"error": str(e)},
                sentinel_decision="ALLOW",
                duration_ms=duration,
            )

    def _build_api_tools(self) -> list[dict[str, Any]]:
        """Convert ToolDefinitions to Anthropic API format."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def _extract_text(self, response: Any) -> str:
        """Extract text content from a response."""
        parts = []
        for block in response.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "\n".join(parts)

    def _serialize_content(self, response: Any) -> list[dict[str, Any]]:
        """Serialize response content blocks for message history."""
        blocks = []
        for block in response.content:
            block_type = getattr(block, "type", "text")
            if block_type == "text":
                blocks.append({"type": "text", "text": block.text})
            elif block_type == "tool_use":
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
        return blocks
