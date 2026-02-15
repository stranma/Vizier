"""Tests for structured logging models."""

from vizier.core.models.logging import AgentLogEntry


class TestAgentLogEntry:
    def test_minimal_creation(self) -> None:
        entry = AgentLogEntry(agent="worker", model="anthropic/claude-sonnet-4-5-20250929")
        assert entry.agent == "worker"
        assert entry.model == "anthropic/claude-sonnet-4-5-20250929"
        assert entry.spec_id is None
        assert entry.tokens_in == 0
        assert entry.tokens_out == 0
        assert entry.duration_ms == 0
        assert entry.cost_usd == 0.0
        assert entry.result == ""
        assert entry.project == ""

    def test_full_creation(self) -> None:
        entry = AgentLogEntry(
            agent="worker",
            spec_id="001-auth/002-jwt",
            model="anthropic/claude-sonnet-4-5-20250929",
            tokens_in=4200,
            tokens_out=1800,
            duration_ms=12500,
            cost_usd=0.042,
            result="REVIEW",
            project="project-alpha",
        )
        assert entry.tokens_in == 4200
        assert entry.tokens_out == 1800
        assert entry.cost_usd == 0.042
        assert entry.result == "REVIEW"

    def test_serialization_roundtrip(self) -> None:
        entry = AgentLogEntry(
            agent="worker",
            model="anthropic/claude-sonnet-4-5-20250929",
            tokens_in=100,
            tokens_out=50,
        )
        data = entry.model_dump()
        restored = AgentLogEntry.model_validate(data)
        assert restored == entry
