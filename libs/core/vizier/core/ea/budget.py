"""Budget enforcement logic (D33): alert, degrade, and pause based on cost thresholds."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from vizier.core.ea.models import BudgetConfig


class BudgetThreshold(StrEnum):
    """Budget threshold levels."""

    NORMAL = "normal"
    ALERT = "alert"
    DEGRADE = "degrade"
    PAUSE = "pause"


class BudgetStatus(BaseModel):
    """Current budget status with spending and threshold info."""

    total_spent_usd: float = 0.0
    monthly_budget_usd: float = 100.0
    usage_ratio: float = 0.0
    threshold: BudgetThreshold = BudgetThreshold.NORMAL
    agent_calls: int = 0
    recommended_tier: str = Field(default="")


class BudgetEnforcer:
    """Enforces cost budget thresholds from agent log data.

    :param config: Budget configuration with thresholds.
    """

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self._config = config or BudgetConfig()

    @property
    def config(self) -> BudgetConfig:
        """Return current budget configuration."""
        return self._config

    def compute_status(self, agent_log_path: str | Path) -> BudgetStatus:
        """Compute current budget status from agent log entries.

        :param agent_log_path: Path to agent-log.jsonl file.
        :returns: Current budget status with threshold determination.
        """
        path = Path(agent_log_path)
        total_cost = 0.0
        agent_calls = 0

        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    total_cost += entry.get("cost_usd", 0.0)
                    agent_calls += 1
                except (json.JSONDecodeError, TypeError):
                    continue

        ratio = total_cost / self._config.monthly_budget_usd if self._config.monthly_budget_usd > 0 else 0.0
        threshold = self._determine_threshold(ratio)
        recommended_tier = self._recommend_tier(threshold)

        return BudgetStatus(
            total_spent_usd=total_cost,
            monthly_budget_usd=self._config.monthly_budget_usd,
            usage_ratio=ratio,
            threshold=threshold,
            agent_calls=agent_calls,
            recommended_tier=recommended_tier,
        )

    def _determine_threshold(self, ratio: float) -> BudgetThreshold:
        """Determine which budget threshold applies for a given usage ratio."""
        if ratio >= self._config.pause_threshold:
            return BudgetThreshold.PAUSE
        if ratio >= self._config.degrade_threshold:
            return BudgetThreshold.DEGRADE
        if ratio >= self._config.alert_threshold:
            return BudgetThreshold.ALERT
        return BudgetThreshold.NORMAL

    def _recommend_tier(self, threshold: BudgetThreshold) -> str:
        """Recommend model tier based on budget threshold."""
        if threshold == BudgetThreshold.DEGRADE:
            return "haiku"
        if threshold == BudgetThreshold.PAUSE:
            return "pause"
        return ""

    def should_allow_work(self, status: BudgetStatus, is_critical: bool = False) -> bool:
        """Determine if new work should be allowed given budget status.

        :param status: Current budget status.
        :param is_critical: Whether the work is critical (ignores pause threshold).
        :returns: True if work should proceed.
        """
        return not (status.threshold == BudgetThreshold.PAUSE and not is_critical)
