"""Graduated retry orchestration for Pasha (D25).

Retry thresholds:
- Retry 1-2: Same model, same decomposition
- Retry 3: Model bump (Sonnet -> Opus for Worker)
- Retry 7: Re-decomposition (send back to Architect)
- Retry 10: Mark as STUCK, escalate to EA
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetryAction(Enum):
    """Action to take based on retry count."""

    RETRY_SAME = "retry_same"
    MODEL_BUMP = "model_bump"
    REDECOMPOSE = "redecompose"
    STUCK = "stuck"


@dataclass
class RetryConfig:
    """Configuration for graduated retry thresholds.

    :param model_bump_at: Retry count at which to bump the model tier.
    :param redecompose_at: Retry count at which to re-decompose the spec.
    :param stuck_at: Retry count at which to mark STUCK and escalate.
    """

    model_bump_at: int = 3
    redecompose_at: int = 7
    stuck_at: int = 10


def determine_retry_action(retry_count: int, config: RetryConfig | None = None) -> RetryAction:
    """Determine the retry action based on retry count (D25).

    :param retry_count: Current retry count (1-based).
    :param config: Optional retry configuration.
    :returns: The action to take for this retry attempt.
    """
    cfg = config or RetryConfig()

    if retry_count >= cfg.stuck_at:
        return RetryAction.STUCK
    if retry_count >= cfg.redecompose_at:
        return RetryAction.REDECOMPOSE
    if retry_count >= cfg.model_bump_at:
        return RetryAction.MODEL_BUMP
    return RetryAction.RETRY_SAME


def get_bumped_model_tier(current_tier: str) -> str:
    """Get the next higher model tier.

    :param current_tier: Current model tier name.
    :returns: Bumped tier name.
    """
    tiers = ["haiku", "sonnet", "opus"]
    try:
        idx = tiers.index(current_tier)
        return tiers[min(idx + 1, len(tiers) - 1)]
    except ValueError:
        return "opus"


@dataclass
class RetryDecision:
    """Complete retry decision with action and context.

    :param action: The retry action to take.
    :param retry_count: Current retry count.
    :param model_tier: Recommended model tier.
    :param reason: Human-readable reason for the action.
    """

    action: RetryAction
    retry_count: int
    model_tier: str
    reason: str


def make_retry_decision(
    retry_count: int,
    current_tier: str = "sonnet",
    config: RetryConfig | None = None,
) -> RetryDecision:
    """Make a complete retry decision with context.

    :param retry_count: Current retry count (1-based).
    :param current_tier: Current model tier.
    :param config: Optional retry configuration.
    :returns: Complete retry decision.
    """
    action = determine_retry_action(retry_count, config)

    if action == RetryAction.STUCK:
        return RetryDecision(
            action=action,
            retry_count=retry_count,
            model_tier=current_tier,
            reason=f"Spec exhausted {retry_count} retries. Marking as STUCK and escalating to EA.",
        )
    if action == RetryAction.REDECOMPOSE:
        return RetryDecision(
            action=action,
            retry_count=retry_count,
            model_tier="opus",
            reason=f"Retry {retry_count}: re-decomposing spec via Architect with Opus tier.",
        )
    if action == RetryAction.MODEL_BUMP:
        bumped = get_bumped_model_tier(current_tier)
        return RetryDecision(
            action=action,
            retry_count=retry_count,
            model_tier=bumped,
            reason=f"Retry {retry_count}: bumping model from {current_tier} to {bumped}.",
        )
    return RetryDecision(
        action=action,
        retry_count=retry_count,
        model_tier=current_tier,
        reason=f"Retry {retry_count}: retrying with same model ({current_tier}).",
    )
