"""Adaptive reconciliation interval (D58).

Adjusts reconciliation frequency based on spec activity:
- Active: 5s (specs being modified)
- Baseline: 15s (default)
- Idle: backoff to 30s -> 60s -> 120s (no changes detected)
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class AdaptiveConfig:
    """Configuration for adaptive reconciliation intervals.

    :param active_interval: Interval when specs are actively changing (seconds).
    :param baseline_interval: Default interval (seconds).
    :param idle_intervals: Backoff sequence when no changes detected (seconds).
    :param idle_threshold: Number of empty reconciliations before backoff starts.
    """

    active_interval: float = 5.0
    baseline_interval: float = 15.0
    idle_intervals: tuple[float, ...] = (30.0, 60.0, 120.0)
    idle_threshold: int = 3


class AdaptiveReconciler:
    """Wraps reconciliation with adaptive interval adjustment.

    Tracks activity (events per reconciliation cycle) and adjusts the
    reconciliation interval accordingly:
    - If events were detected -> active interval (fastest)
    - If no events for < idle_threshold cycles -> baseline
    - If no events for >= idle_threshold cycles -> backoff through idle_intervals

    :param config: Adaptive interval configuration.
    """

    def __init__(self, config: AdaptiveConfig | None = None) -> None:
        self._config = config or AdaptiveConfig()
        self._idle_count = 0
        self._last_activity_time = time.monotonic()

    @property
    def current_interval(self) -> float:
        """Return the current reconciliation interval in seconds."""
        if self._idle_count == 0:
            return self._config.active_interval

        if self._idle_count < self._config.idle_threshold:
            return self._config.baseline_interval

        backoff_index = min(
            self._idle_count - self._config.idle_threshold,
            len(self._config.idle_intervals) - 1,
        )
        return self._config.idle_intervals[backoff_index]

    @property
    def idle_count(self) -> int:
        """Number of consecutive idle (no events) reconciliation cycles."""
        return self._idle_count

    @property
    def seconds_since_activity(self) -> float:
        """Seconds elapsed since last detected activity."""
        return time.monotonic() - self._last_activity_time

    def record_cycle(self, event_count: int) -> float:
        """Record a reconciliation cycle result and return next interval.

        :param event_count: Number of events detected in this cycle.
        :returns: The next interval to use (seconds).
        """
        if event_count > 0:
            self._idle_count = 0
            self._last_activity_time = time.monotonic()
        else:
            self._idle_count += 1

        return self.current_interval

    def reset(self) -> None:
        """Reset to baseline state."""
        self._idle_count = 0
        self._last_activity_time = time.monotonic()
