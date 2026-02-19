"""Tests for graduated retry orchestration (D25)."""

from vizier.core.agents.pasha.retry import (
    RetryAction,
    RetryConfig,
    determine_retry_action,
    get_bumped_model_tier,
    make_retry_decision,
)


class TestDetermineRetryAction:
    def test_retry_1_same(self) -> None:
        assert determine_retry_action(1) == RetryAction.RETRY_SAME

    def test_retry_2_same(self) -> None:
        assert determine_retry_action(2) == RetryAction.RETRY_SAME

    def test_retry_3_model_bump(self) -> None:
        assert determine_retry_action(3) == RetryAction.MODEL_BUMP

    def test_retry_5_model_bump(self) -> None:
        assert determine_retry_action(5) == RetryAction.MODEL_BUMP

    def test_retry_7_redecompose(self) -> None:
        assert determine_retry_action(7) == RetryAction.REDECOMPOSE

    def test_retry_9_redecompose(self) -> None:
        assert determine_retry_action(9) == RetryAction.REDECOMPOSE

    def test_retry_10_stuck(self) -> None:
        assert determine_retry_action(10) == RetryAction.STUCK

    def test_retry_15_stuck(self) -> None:
        assert determine_retry_action(15) == RetryAction.STUCK

    def test_custom_config(self) -> None:
        config = RetryConfig(model_bump_at=2, redecompose_at=5, stuck_at=8)
        assert determine_retry_action(1, config) == RetryAction.RETRY_SAME
        assert determine_retry_action(2, config) == RetryAction.MODEL_BUMP
        assert determine_retry_action(5, config) == RetryAction.REDECOMPOSE
        assert determine_retry_action(8, config) == RetryAction.STUCK


class TestGetBumpedModelTier:
    def test_haiku_to_sonnet(self) -> None:
        assert get_bumped_model_tier("haiku") == "sonnet"

    def test_sonnet_to_opus(self) -> None:
        assert get_bumped_model_tier("sonnet") == "opus"

    def test_opus_stays_opus(self) -> None:
        assert get_bumped_model_tier("opus") == "opus"

    def test_unknown_to_opus(self) -> None:
        assert get_bumped_model_tier("unknown") == "opus"


class TestMakeRetryDecision:
    def test_same_model_decision(self) -> None:
        decision = make_retry_decision(1, "sonnet")
        assert decision.action == RetryAction.RETRY_SAME
        assert decision.model_tier == "sonnet"
        assert "same model" in decision.reason.lower()

    def test_model_bump_decision(self) -> None:
        decision = make_retry_decision(3, "sonnet")
        assert decision.action == RetryAction.MODEL_BUMP
        assert decision.model_tier == "opus"
        assert "bumping" in decision.reason.lower()

    def test_redecompose_decision(self) -> None:
        decision = make_retry_decision(7, "sonnet")
        assert decision.action == RetryAction.REDECOMPOSE
        assert decision.model_tier == "opus"
        assert "re-decomposing" in decision.reason.lower()

    def test_stuck_decision(self) -> None:
        decision = make_retry_decision(10, "opus")
        assert decision.action == RetryAction.STUCK
        assert "STUCK" in decision.reason
        assert "escalating" in decision.reason.lower()

    def test_retry_count_preserved(self) -> None:
        decision = make_retry_decision(5, "sonnet")
        assert decision.retry_count == 5
