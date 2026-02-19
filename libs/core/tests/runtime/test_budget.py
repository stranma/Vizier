"""Tests for BudgetTracker."""

import logging

import pytest

from vizier.core.runtime.budget import BudgetConfig, BudgetTracker


class TestBudgetConfig:
    def test_defaults(self) -> None:
        config = BudgetConfig()
        assert config.max_tokens == 100_000
        assert config.warn_threshold == 0.8
        assert config.max_turns == 50

    def test_custom(self) -> None:
        config = BudgetConfig(max_tokens=50_000, warn_threshold=0.9, max_turns=20)
        assert config.max_tokens == 50_000
        assert config.warn_threshold == 0.9
        assert config.max_turns == 20


class TestBudgetTracker:
    def test_initial_state(self) -> None:
        tracker = BudgetTracker()
        assert tracker.tokens_used == 0
        assert tracker.turns == 0
        assert tracker.tokens_remaining == 100_000
        assert tracker.budget_fraction == 0.0
        assert not tracker.is_exhausted()

    def test_record_usage(self) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=1000))
        tracker.record_usage(input_tokens=100, output_tokens=50)
        assert tracker.tokens_used == 150
        assert tracker.turns == 1
        assert tracker.tokens_remaining == 850
        assert tracker.budget_fraction == 0.15

    def test_token_exhaustion(self) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=200))
        tracker.record_usage(100, 50)
        assert not tracker.is_exhausted()
        tracker.record_usage(100, 50)
        assert tracker.is_exhausted()

    def test_turn_exhaustion(self) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=1_000_000, max_turns=2))
        tracker.record_usage(10, 10)
        assert not tracker.is_exhausted()
        tracker.record_usage(10, 10)
        assert tracker.is_exhausted()

    def test_reset(self) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=1000))
        tracker.record_usage(500, 300)
        assert tracker.tokens_used == 800
        assert tracker.turns == 1
        tracker.reset()
        assert tracker.tokens_used == 0
        assert tracker.turns == 0
        assert not tracker.is_exhausted()

    def test_warn_threshold_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=100, warn_threshold=0.8))
        with caplog.at_level(logging.WARNING):
            tracker.record_usage(40, 0)
            assert len(caplog.records) == 0
            tracker.record_usage(45, 0)
            assert len(caplog.records) == 1
            assert "Budget warning" in caplog.records[0].message

    def test_zero_max_tokens(self) -> None:
        tracker = BudgetTracker(BudgetConfig(max_tokens=0))
        assert tracker.budget_fraction == 1.0
        assert tracker.is_exhausted()
