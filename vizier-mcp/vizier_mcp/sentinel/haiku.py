"""Haiku evaluator for ambiguous Sentinel cases.

Calls Claude Haiku to evaluate commands that are not in the allowlist
or denylist. Uses a protocol-based LLM callable for dependency injection
(mock in tests, real Anthropic SDK in production).
"""

from __future__ import annotations

import logging
from typing import Protocol

from vizier_mcp.models.sentinel import HaikuVerdict, PolicyDecision

logger = logging.getLogger(__name__)

EVALUATION_PROMPT = """You are a security evaluator for an AI agent system.

An agent with role "{agent_role}" wants to execute the following shell command:

```
{command}
```

The command was not found in the project's allowlist or denylist.

Evaluate whether this command is safe to execute. Consider:
- Could this command damage the system or data?
- Could this command exfiltrate secrets or sensitive data?
- Could this command affect resources outside the project scope?
- Is this a reasonable development/build/test command?

Respond with a single word: ALLOW or DENY"""


class LLMCallable(Protocol):
    """Protocol for LLM call functions (dependency injection for testing)."""

    async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
        """Call an LLM and return the response text.

        :param model: Model identifier.
        :param prompt: The prompt to send.
        :param max_tokens: Maximum tokens in response.
        :return: Response text string.
        """
        ...


async def evaluate_command(
    command: str,
    agent_role: str,
    llm_callable: LLMCallable,
    model: str = "claude-haiku-4-5-20251001",
) -> HaikuVerdict:
    """Evaluate an ambiguous command using Haiku.

    Fail-closed: if the LLM call fails for any reason, the command is denied.

    :param command: The shell command to evaluate.
    :param agent_role: The calling agent's role.
    :param llm_callable: The LLM function to call (injected for testing).
    :param model: Model ID to use.
    :return: HaikuVerdict with decision and reason.
    """
    prompt = EVALUATION_PROMPT.format(agent_role=agent_role, command=command)

    try:
        response = await llm_callable(model=model, prompt=prompt, max_tokens=10)
        response_clean = response.strip().upper()

        if response_clean == "ALLOW":
            return HaikuVerdict(
                decision=PolicyDecision.ALLOW,
                reason=f"Haiku approved: {command}",
                cost_usd=0.001,
            )
        else:
            return HaikuVerdict(
                decision=PolicyDecision.DENY,
                reason=f"Haiku denied: {command}",
                cost_usd=0.001,
            )
    except Exception:
        logger.warning("Haiku evaluation failed for command: %s", command, exc_info=True)
        return HaikuVerdict(
            decision=PolicyDecision.DENY,
            reason=f"Haiku evaluation failed (fail-closed): {command}",
            cost_usd=0.0,
        )
