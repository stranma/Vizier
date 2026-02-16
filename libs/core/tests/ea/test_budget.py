"""Tests for budget enforcement logic."""

import json
from pathlib import Path

from vizier.core.ea.budget import BudgetEnforcer, BudgetStatus, BudgetThreshold
from vizier.core.ea.models import BudgetConfig


class TestBudgetThresholds:
    def test_normal_threshold(self) -> None:
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        assert enforcer._determine_threshold(0.5) == BudgetThreshold.NORMAL

    def test_alert_threshold(self) -> None:
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        assert enforcer._determine_threshold(0.85) == BudgetThreshold.ALERT

    def test_degrade_threshold(self) -> None:
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        assert enforcer._determine_threshold(1.05) == BudgetThreshold.DEGRADE

    def test_pause_threshold(self) -> None:
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        assert enforcer._determine_threshold(1.3) == BudgetThreshold.PAUSE


class TestBudgetEnforcer:
    def test_empty_log(self, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        log_path.write_text("", encoding="utf-8")
        enforcer = BudgetEnforcer()
        status = enforcer.compute_status(log_path)
        assert status.total_spent_usd == 0.0
        assert status.threshold == BudgetThreshold.NORMAL

    def test_missing_log(self, tmp_path: Path) -> None:
        log_path = tmp_path / "nonexistent.jsonl"
        enforcer = BudgetEnforcer()
        status = enforcer.compute_status(log_path)
        assert status.total_spent_usd == 0.0

    def test_computes_cost_from_entries(self, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        entries = [
            {"agent": "worker", "cost_usd": 0.05},
            {"agent": "quality_gate", "cost_usd": 0.03},
            {"agent": "architect", "cost_usd": 0.10},
        ]
        log_path.write_text("\n".join(json.dumps(e) for e in entries), encoding="utf-8")
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=1.0))
        status = enforcer.compute_status(log_path)
        assert abs(status.total_spent_usd - 0.18) < 0.001
        assert status.agent_calls == 3

    def test_alert_threshold_triggered(self, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        entries = [{"agent": "worker", "cost_usd": 85.0}]
        log_path.write_text(json.dumps(entries[0]), encoding="utf-8")
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        status = enforcer.compute_status(log_path)
        assert status.threshold == BudgetThreshold.ALERT

    def test_degrade_recommends_haiku(self, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        entries = [{"agent": "worker", "cost_usd": 105.0}]
        log_path.write_text(json.dumps(entries[0]), encoding="utf-8")
        enforcer = BudgetEnforcer(BudgetConfig(monthly_budget_usd=100.0))
        status = enforcer.compute_status(log_path)
        assert status.threshold == BudgetThreshold.DEGRADE
        assert status.recommended_tier == "haiku"

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        log_path.write_text('{"cost_usd": 0.05}\nnot json\n{"cost_usd": 0.03}\n', encoding="utf-8")
        enforcer = BudgetEnforcer()
        status = enforcer.compute_status(log_path)
        assert abs(status.total_spent_usd - 0.08) < 0.001
        assert status.agent_calls == 2


class TestShouldAllowWork:
    def test_normal_allows(self) -> None:
        enforcer = BudgetEnforcer()
        status = BudgetStatus(threshold=BudgetThreshold.NORMAL)
        assert enforcer.should_allow_work(status) is True

    def test_pause_blocks_noncritical(self) -> None:
        enforcer = BudgetEnforcer()
        status = BudgetStatus(threshold=BudgetThreshold.PAUSE)
        assert enforcer.should_allow_work(status) is False

    def test_pause_allows_critical(self) -> None:
        enforcer = BudgetEnforcer()
        status = BudgetStatus(threshold=BudgetThreshold.PAUSE)
        assert enforcer.should_allow_work(status, is_critical=True) is True

    def test_degrade_allows(self) -> None:
        enforcer = BudgetEnforcer()
        status = BudgetStatus(threshold=BudgetThreshold.DEGRADE)
        assert enforcer.should_allow_work(status) is True
