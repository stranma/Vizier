"""Tests for graduated retry logic."""

from __future__ import annotations

from vizier.core.lifecycle.retry import GraduatedRetry, RetryAction, RetryThreshold


class TestRetryThresholds:
    def test_default_thresholds(self) -> None:
        t = RetryThreshold()
        assert t.bump_model_at == 3
        assert t.alert_pasha_at == 5
        assert t.re_decompose_at == 7
        assert t.stuck_at == 10
        assert t.repeated_action_limit == 3

    def test_custom_thresholds(self) -> None:
        t = RetryThreshold(bump_model_at=2, stuck_at=5)
        assert t.bump_model_at == 2
        assert t.stuck_at == 5


class TestGraduatedRetry:
    def test_low_retries_continue(self) -> None:
        retry = GraduatedRetry()
        assert retry.evaluate(0) == RetryAction.CONTINUE
        assert retry.evaluate(1) == RetryAction.CONTINUE
        assert retry.evaluate(2) == RetryAction.CONTINUE

    def test_retry_3_bumps_model(self) -> None:
        retry = GraduatedRetry()
        assert retry.evaluate(3) == RetryAction.BUMP_MODEL
        assert retry.evaluate(4) == RetryAction.BUMP_MODEL

    def test_retry_5_alerts_pasha(self) -> None:
        retry = GraduatedRetry()
        assert retry.evaluate(5) == RetryAction.ALERT_PASHA
        assert retry.evaluate(6) == RetryAction.ALERT_PASHA

    def test_retry_7_re_decomposes(self) -> None:
        retry = GraduatedRetry()
        assert retry.evaluate(7) == RetryAction.RE_DECOMPOSE
        assert retry.evaluate(8) == RetryAction.RE_DECOMPOSE
        assert retry.evaluate(9) == RetryAction.RE_DECOMPOSE

    def test_retry_10_stuck(self) -> None:
        retry = GraduatedRetry()
        assert retry.evaluate(10) == RetryAction.STUCK
        assert retry.evaluate(15) == RetryAction.STUCK

    def test_custom_thresholds(self) -> None:
        retry = GraduatedRetry(RetryThreshold(bump_model_at=2, stuck_at=4))
        assert retry.evaluate(1) == RetryAction.CONTINUE
        assert retry.evaluate(2) == RetryAction.BUMP_MODEL
        assert retry.evaluate(4) == RetryAction.STUCK


class TestRepeatedActionDetection:
    def test_no_repeated_actions(self) -> None:
        retry = GraduatedRetry()
        assert retry.check_repeated_actions(["a", "b", "c"]) is False

    def test_repeated_actions_detected(self) -> None:
        retry = GraduatedRetry()
        assert retry.check_repeated_actions(["a", "a", "a"]) is True

    def test_not_enough_actions(self) -> None:
        retry = GraduatedRetry()
        assert retry.check_repeated_actions(["a", "a"]) is False

    def test_only_last_n_matter(self) -> None:
        retry = GraduatedRetry()
        assert retry.check_repeated_actions(["x", "y", "a", "a", "a"]) is True

    def test_custom_limit(self) -> None:
        retry = GraduatedRetry(RetryThreshold(repeated_action_limit=2))
        assert retry.check_repeated_actions(["a", "a"]) is True
        assert retry.check_repeated_actions(["a", "b"]) is False


class TestModelTierBumping:
    def test_haiku_to_sonnet(self) -> None:
        retry = GraduatedRetry()
        assert retry.get_bumped_tier("haiku") == "sonnet"

    def test_sonnet_to_opus(self) -> None:
        retry = GraduatedRetry()
        assert retry.get_bumped_tier("sonnet") == "opus"

    def test_opus_stays_opus(self) -> None:
        retry = GraduatedRetry()
        assert retry.get_bumped_tier("opus") == "opus"

    def test_unknown_tier_unchanged(self) -> None:
        retry = GraduatedRetry()
        assert retry.get_bumped_tier("unknown") == "unknown"
