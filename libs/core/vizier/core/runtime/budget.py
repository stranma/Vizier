"""Budget tracking for agent runs (D33)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BudgetConfig:
    """Budget limits for an agent run.

    :param max_tokens: Maximum total tokens (input + output) before exhaustion.
    :param warn_threshold: Fraction (0-1) at which to emit a warning log.
    :param max_turns: Maximum number of API round-trips.
    """

    max_tokens: int = 100_000
    warn_threshold: float = 0.8
    max_turns: int = 50


class BudgetTracker:
    """Tracks token usage against budget limits.

    :param config: Budget configuration. Uses defaults if not provided.
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()
        self._tokens_used = 0
        self._turns = 0

    @property
    def tokens_used(self) -> int:
        """Total tokens consumed so far."""
        return self._tokens_used

    @property
    def turns(self) -> int:
        """Number of API round-trips completed."""
        return self._turns

    @property
    def tokens_remaining(self) -> int:
        """Tokens remaining before budget exhaustion."""
        return max(0, self._config.max_tokens - self._tokens_used)

    @property
    def budget_fraction(self) -> float:
        """Fraction of token budget consumed (0.0 to 1.0+)."""
        if self._config.max_tokens <= 0:
            return 1.0
        return self._tokens_used / self._config.max_tokens

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from an API response.

        :param input_tokens: Input tokens from response.usage.
        :param output_tokens: Output tokens from response.usage.
        """
        self._tokens_used += input_tokens + output_tokens
        self._turns += 1

        if self.budget_fraction >= self._config.warn_threshold:
            logger.warning(
                "Budget warning: %.0f%% used (%d/%d tokens, turn %d/%d)",
                self.budget_fraction * 100,
                self._tokens_used,
                self._config.max_tokens,
                self._turns,
                self._config.max_turns,
            )

    def is_exhausted(self) -> bool:
        """Check if budget is exhausted (tokens or turns)."""
        return self._tokens_used >= self._config.max_tokens or self._turns >= self._config.max_turns

    def reset(self) -> None:
        """Reset tracking for a new run."""
        self._tokens_used = 0
        self._turns = 0
