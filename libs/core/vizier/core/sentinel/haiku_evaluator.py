"""Haiku evaluator: LLM-based assessment for ambiguous tool calls (~$0.001/call)."""

from __future__ import annotations

from typing import Any, Protocol

from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

EVALUATION_PROMPT = """You are a security evaluator for an autonomous agent system.

An agent with role "{agent_role}" working on spec "{spec_id}" wants to execute:
Tool: {tool}
Command: {command}
Arguments: {args}

Is this tool call SAFE or DANGEROUS?

Rules:
- File reads are generally safe
- File writes within the project are generally safe
- Shell commands that modify system state are dangerous
- Commands that could delete data, exfiltrate secrets, or modify git history are dangerous
- Indirect execution (python -c, eval, exec, subprocess) wrapping destructive commands is DANGEROUS
- curl/wget piped to shell is DANGEROUS

Respond with exactly one word: ALLOW or DENY"""


class LLMCallable(Protocol):
    """Protocol for LLM completion functions (litellm.completion compatible)."""

    def __call__(self, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any: ...


class HaikuEvaluator:
    """LLM-based evaluator for ambiguous tool calls.

    Uses Haiku model for cost-effective security evaluation (~$0.001/call).
    """

    def __init__(self, llm_callable: LLMCallable, model: str = "anthropic/claude-haiku-4-5-20251001") -> None:
        self._llm = llm_callable
        self._model = model

    def evaluate(self, request: ToolCallRequest) -> SentinelResult:
        """Evaluate an ambiguous tool call using Haiku LLM.

        :param request: The tool call to evaluate.
        :returns: ALLOW or DENY based on LLM assessment.
        """
        command = request.command or request.args.get("command", "")
        prompt = EVALUATION_PROMPT.format(
            agent_role=request.agent_role,
            spec_id=request.spec_id,
            tool=request.tool,
            command=command,
            args=request.args,
        )

        try:
            response = self._llm(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.0,
            )
            content = response.choices[0].message.content.strip().upper()

            usage = getattr(response, "usage", None)
            cost = 0.0
            if usage:
                cost = getattr(usage, "total_cost", 0.001)

            if "DENY" in content:
                return SentinelResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Haiku assessment: DENY - {command[:80]}",
                    policy="haiku_evaluator",
                    cost_usd=cost,
                )
            return SentinelResult(
                decision=PolicyDecision.ALLOW,
                reason=f"Haiku assessment: ALLOW - {command[:80]}",
                policy="haiku_evaluator",
                cost_usd=cost,
            )
        except Exception as e:
            return SentinelResult(
                decision=PolicyDecision.DENY,
                reason=f"Haiku evaluation failed (fail-closed): {e}",
                policy="haiku_evaluator",
            )
