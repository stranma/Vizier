"""Tests for adaptive reconciliation interval (D58)."""

from __future__ import annotations

from vizier.core.watcher.adaptive import AdaptiveConfig, AdaptiveReconciler


class TestAdaptiveReconciler:
    def test_starts_at_baseline(self) -> None:
        ar = AdaptiveReconciler()
        ar._idle_count = 1
        assert ar.current_interval == 15.0

    def test_active_after_events(self) -> None:
        ar = AdaptiveReconciler()
        interval = ar.record_cycle(event_count=3)
        assert interval == 5.0
        assert ar.idle_count == 0

    def test_idle_backoff(self) -> None:
        ar = AdaptiveReconciler()
        ar.record_cycle(event_count=1)
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 15.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 15.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 30.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 60.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 120.0

    def test_idle_backoff_caps_at_max(self) -> None:
        ar = AdaptiveReconciler()
        for _ in range(20):
            ar.record_cycle(event_count=0)
        assert ar.current_interval == 120.0

    def test_activity_resets_backoff(self) -> None:
        ar = AdaptiveReconciler()
        for _ in range(10):
            ar.record_cycle(event_count=0)
        assert ar.current_interval == 120.0
        ar.record_cycle(event_count=1)
        assert ar.current_interval == 5.0
        assert ar.idle_count == 0

    def test_reset(self) -> None:
        ar = AdaptiveReconciler()
        for _ in range(10):
            ar.record_cycle(event_count=0)
        ar.reset()
        assert ar.idle_count == 0

    def test_custom_config(self) -> None:
        config = AdaptiveConfig(
            active_interval=2.0,
            baseline_interval=10.0,
            idle_intervals=(20.0, 40.0),
            idle_threshold=2,
        )
        ar = AdaptiveReconciler(config)
        ar.record_cycle(event_count=1)
        assert ar.current_interval == 2.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 10.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 20.0
        ar.record_cycle(event_count=0)
        assert ar.current_interval == 40.0

    def test_seconds_since_activity(self) -> None:
        ar = AdaptiveReconciler()
        ar.record_cycle(event_count=1)
        assert ar.seconds_since_activity < 1.0

    def test_record_returns_next_interval(self) -> None:
        ar = AdaptiveReconciler()
        interval = ar.record_cycle(event_count=5)
        assert interval == 5.0
        interval = ar.record_cycle(event_count=0)
        assert interval == 15.0
