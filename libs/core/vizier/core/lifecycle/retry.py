"""Graduated retry logic (D25).

Thresholds:
    Retries 1-2: normal with Quality Gate feedback
    Retry 3: bump Worker model tier
    Retry 5: alert Pasha for spec review
    Retry 7: Architect re-decomposes
    Retry 10: STUCK

Repeated action detection (D25/BudgetMLAgent):
    If Worker performs identical tool call 3+ consecutive times,
    escalate immediately to next threshold.
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger(__name__)


class RetryAction(StrEnum):
    """Actions from graduated retry evaluation."""

    CONTINUE = "continue"
    BUMP_MODEL = "bump_model"
    ALERT_PASHA = "alert_pasha"
    RE_DECOMPOSE = "re_decompose"
    STUCK = "stuck"


class RetryThreshold:
    """Configurable retry thresholds.

    :param bump_model_at: Retry count at which to bump model tier.
    :param alert_pasha_at: Retry count at which to alert Pasha.
    :param re_decompose_at: Retry count at which to trigger re-decomposition.
    :param stuck_at: Maximum retry count before STUCK.
    :param repeated_action_limit: Consecutive identical tool calls before escalation.
    """

    def __init__(
        self,
        bump_model_at: int = 3,
        alert_pasha_at: int = 5,
        re_decompose_at: int = 7,
        stuck_at: int = 10,
        repeated_action_limit: int = 3,
    ) -> None:
        self.bump_model_at = bump_model_at
        self.alert_pasha_at = alert_pasha_at
        self.re_decompose_at = re_decompose_at
        self.stuck_at = stuck_at
        self.repeated_action_limit = repeated_action_limit


class GraduatedRetry:
    """Evaluates retry count and returns the appropriate action.

    :param thresholds: Custom retry thresholds (optional).
    """

    def __init__(self, thresholds: RetryThreshold | None = None) -> None:
        self._thresholds = thresholds or RetryThreshold()

    @property
    def thresholds(self) -> RetryThreshold:
        return self._thresholds

    def evaluate(self, retry_count: int) -> RetryAction:
        """Determine the action for a given retry count.

        :param retry_count: Current retry count (incremented from 0).
        :returns: The action to take.
        """
        t = self._thresholds

        if retry_count >= t.stuck_at:
            logger.warning("Spec stuck after %d retries", retry_count)
            return RetryAction.STUCK

        if retry_count >= t.re_decompose_at:
            logger.info("Retry %d: triggering re-decomposition", retry_count)
            return RetryAction.RE_DECOMPOSE

        if retry_count >= t.alert_pasha_at:
            logger.info("Retry %d: alerting Pasha for spec review", retry_count)
            return RetryAction.ALERT_PASHA

        if retry_count >= t.bump_model_at:
            logger.info("Retry %d: bumping Worker model tier", retry_count)
            return RetryAction.BUMP_MODEL

        return RetryAction.CONTINUE

    def check_repeated_actions(self, recent_actions: list[str]) -> bool:
        """Detect if Worker is stuck in a loop.

        :param recent_actions: List of recent tool call signatures.
        :returns: True if repeated action threshold is exceeded.
        """
        limit = self._thresholds.repeated_action_limit
        if len(recent_actions) < limit:
            return False

        last_n = recent_actions[-limit:]
        if len(set(last_n)) == 1:
            logger.warning("Repeated action detected: %s (x%d)", last_n[0], limit)
            return True

        return False

    def get_bumped_tier(self, current_tier: str) -> str:
        """Return the next model tier up from the current one.

        :param current_tier: Current model tier name.
        :returns: Upgraded tier name.
        """
        tier_order = ["haiku", "sonnet", "opus"]
        try:
            idx = tier_order.index(current_tier)
            if idx < len(tier_order) - 1:
                return tier_order[idx + 1]
        except ValueError:
            pass
        return current_tier
