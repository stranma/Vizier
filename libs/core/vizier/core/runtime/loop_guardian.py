"""Loop Guardian: detects agent spinning via checkpoints and repeat detection (D51)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

LLMCheckpointCallable = Callable[[str], "GuardianVerdict | str"]


class GuardianVerdict(StrEnum):
    """Verdict from a Loop Guardian checkpoint."""

    CONTINUE = "CONTINUE"
    WARN = "WARN"
    HALT = "HALT"


@dataclass
class GuardianConfig:
    """Configuration for the Loop Guardian.

    :param checkpoint_interval: Run LLM checkpoint every N tool calls.
    :param max_identical_calls: Halt after this many identical consecutive tool calls.
    :param enabled: Whether the guardian is active.
    """

    checkpoint_interval: int = 5
    max_identical_calls: int = 3
    enabled: bool = True


@dataclass
class ToolCallSummary:
    """Compact summary of a tool call for guardian analysis."""

    tool_name: str
    tool_input_hash: str
    success: bool
    result_preview: str = ""


class LoopGuardian:
    """Monitors agent tool call patterns and triggers checkpoints.

    Two detection mechanisms:
    1. **Deterministic repeat detection**: If the same tool call (name + input hash)
       appears max_identical_calls times consecutively, immediately HALT.
    2. **LLM checkpoint**: Every checkpoint_interval tool calls, sends a summary of
       recent calls to a Haiku-tier model to evaluate progress.

    :param config: Guardian configuration.
    :param llm_checkpoint: Optional callable for LLM-based checkpoint evaluation.
        Signature: (recent_calls_summary: str) -> GuardianVerdict.
        If not provided, only deterministic detection is active.
    """

    def __init__(
        self,
        config: GuardianConfig | None = None,
        llm_checkpoint: LLMCheckpointCallable | None = None,
    ) -> None:
        self._config = config or GuardianConfig()
        self._llm_checkpoint = llm_checkpoint
        self._call_history: list[ToolCallSummary] = []
        self._total_calls = 0

    @property
    def total_calls(self) -> int:
        """Total tool calls observed."""
        return self._total_calls

    @property
    def call_history(self) -> list[ToolCallSummary]:
        """Recent call history."""
        return list(self._call_history)

    def record_call(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        success: bool,
        result_preview: str = "",
    ) -> GuardianVerdict:
        """Record a tool call and check for spinning.

        :param tool_name: Name of the tool called.
        :param tool_input: Input arguments to the tool.
        :param success: Whether the tool call succeeded.
        :param result_preview: Short preview of the result.
        :returns: Verdict (CONTINUE, WARN, or HALT).
        """
        if not self._config.enabled:
            return GuardianVerdict.CONTINUE

        input_hash = _hash_input(tool_name, tool_input)
        summary = ToolCallSummary(
            tool_name=tool_name,
            tool_input_hash=input_hash,
            success=success,
            result_preview=result_preview[:200],
        )
        self._call_history.append(summary)
        self._total_calls += 1

        repeat_verdict = self._check_repeats()
        if repeat_verdict != GuardianVerdict.CONTINUE:
            return repeat_verdict

        if self._should_checkpoint():
            return self._run_checkpoint()

        return GuardianVerdict.CONTINUE

    def _check_repeats(self) -> GuardianVerdict:
        """Deterministic check: same tool+input repeated consecutively."""
        threshold = self._config.max_identical_calls
        if len(self._call_history) < threshold:
            return GuardianVerdict.CONTINUE

        recent = self._call_history[-threshold:]
        first_hash = recent[0].tool_input_hash
        if all(c.tool_input_hash == first_hash for c in recent):
            logger.warning(
                "Loop Guardian: identical tool call repeated %d times: %s",
                threshold,
                recent[0].tool_name,
            )
            return GuardianVerdict.HALT

        return GuardianVerdict.CONTINUE

    def _should_checkpoint(self) -> bool:
        """Check if it's time for an LLM checkpoint."""
        if self._llm_checkpoint is None:
            return False
        return self._total_calls > 0 and self._total_calls % self._config.checkpoint_interval == 0

    def _run_checkpoint(self) -> GuardianVerdict:
        """Run LLM checkpoint on recent tool call history."""
        if self._llm_checkpoint is None:
            return GuardianVerdict.CONTINUE

        window = self._call_history[-self._config.checkpoint_interval :]
        summary = _format_call_summary(window)

        try:
            verdict = self._llm_checkpoint(summary)
            if isinstance(verdict, str):
                verdict = GuardianVerdict(verdict)
            logger.info("Loop Guardian checkpoint: %s", verdict)
            return verdict
        except Exception:
            logger.warning("Loop Guardian checkpoint failed, defaulting to CONTINUE")
            return GuardianVerdict.CONTINUE

    def reset(self) -> None:
        """Reset the guardian state for a new run."""
        self._call_history.clear()
        self._total_calls = 0


def _hash_input(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Create a deterministic hash of tool name + input for comparison."""
    canonical = json.dumps({"tool": tool_name, "input": tool_input}, sort_keys=True, default=str)
    return canonical


def _format_call_summary(calls: list[ToolCallSummary]) -> str:
    """Format call history into a human-readable summary for LLM checkpoint."""
    lines = []
    for i, call in enumerate(calls, 1):
        status = "OK" if call.success else "FAIL"
        preview = f" -> {call.result_preview}" if call.result_preview else ""
        lines.append(f"{i}. {call.tool_name} [{status}]{preview}")
    return "\n".join(lines)
