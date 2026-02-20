"""Tests for the Haiku evaluator (AC-S5, AC-S9)."""

from __future__ import annotations

import pytest

from vizier_mcp.models.sentinel import PolicyDecision
from vizier_mcp.sentinel.haiku import evaluate_command


class MockLLMAllow:
    """Mock LLM that always returns ALLOW."""

    async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
        return "ALLOW"


class MockLLMDeny:
    """Mock LLM that always returns DENY."""

    async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
        return "DENY"


class MockLLMFailing:
    """Mock LLM that raises an exception."""

    async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
        raise RuntimeError("API connection failed")


class MockLLMGarbage:
    """Mock LLM that returns garbage response."""

    async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
        return "I don't understand"


class TestHaikuEvaluator:
    """Tests for Haiku evaluation of ambiguous commands."""

    @pytest.mark.anyio
    async def test_allow_response(self) -> None:
        verdict = await evaluate_command("curl http://example.com", "worker", MockLLMAllow())
        assert verdict.decision == PolicyDecision.ALLOW
        assert verdict.cost_usd > 0

    @pytest.mark.anyio
    async def test_deny_response(self) -> None:
        verdict = await evaluate_command("nmap localhost", "worker", MockLLMDeny())
        assert verdict.decision == PolicyDecision.DENY
        assert verdict.cost_usd > 0

    @pytest.mark.anyio
    async def test_fail_closed_on_exception(self) -> None:
        verdict = await evaluate_command("curl http://example.com", "worker", MockLLMFailing())
        assert verdict.decision == PolicyDecision.DENY
        assert "fail-closed" in verdict.reason.lower()

    @pytest.mark.anyio
    async def test_garbage_response_denied(self) -> None:
        verdict = await evaluate_command("some command", "worker", MockLLMGarbage())
        assert verdict.decision == PolicyDecision.DENY

    @pytest.mark.anyio
    async def test_prompt_contains_command_and_role(self) -> None:
        captured_prompt = None

        class MockLLMCapture:
            async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
                nonlocal captured_prompt
                captured_prompt = prompt
                return "ALLOW"

        await evaluate_command("pip install requests", "worker", MockLLMCapture())
        assert captured_prompt is not None
        assert "pip install requests" in captured_prompt
        assert "worker" in captured_prompt

    @pytest.mark.anyio
    async def test_custom_model(self) -> None:
        captured_model = None

        class MockLLMCaptureModel:
            async def __call__(self, model: str, prompt: str, max_tokens: int = 10) -> str:
                nonlocal captured_model
                captured_model = model
                return "ALLOW"

        await evaluate_command("test", "worker", MockLLMCaptureModel(), model="custom-model")
        assert captured_model == "custom-model"
