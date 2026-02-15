"""Tests for structured agent logging."""

from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.models.logging import AgentLogEntry


class TestAgentLogger:
    def test_log_creates_file(self, tmp_path) -> None:
        log_path = tmp_path / "reports" / "test" / "agent-log.jsonl"
        logger = AgentLogger(log_path)
        entry = AgentLogEntry(agent="worker", model="test-model", tokens_in=100, tokens_out=50)
        logger.log(entry)
        assert log_path.exists()

    def test_log_appends(self, tmp_path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        logger = AgentLogger(log_path)
        logger.log(AgentLogEntry(agent="worker", model="m1"))
        logger.log(AgentLogEntry(agent="architect", model="m2"))
        entries = logger.read_entries()
        assert len(entries) == 2
        assert entries[0].agent == "worker"
        assert entries[1].agent == "architect"

    def test_read_empty(self, tmp_path) -> None:
        logger = AgentLogger(tmp_path / "nonexistent.jsonl")
        assert logger.read_entries() == []

    def test_entry_roundtrip(self, tmp_path) -> None:
        log_path = tmp_path / "agent-log.jsonl"
        logger = AgentLogger(log_path)
        original = AgentLogEntry(
            agent="worker",
            spec_id="001-test",
            model="anthropic/claude-sonnet-4-5-20250929",
            tokens_in=4200,
            tokens_out=1800,
            duration_ms=12500,
            cost_usd=0.042,
            result="REVIEW",
            project="project-alpha",
        )
        logger.log(original)
        entries = logger.read_entries()
        assert len(entries) == 1
        assert entries[0].agent == original.agent
        assert entries[0].tokens_in == original.tokens_in
        assert entries[0].cost_usd == original.cost_usd


class TestEntryFromLitellmResponse:
    def test_extracts_usage(self) -> None:
        response = {
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
            "response_cost": 0.025,
        }
        entry = AgentLogger.entry_from_litellm_response(
            response=response,
            agent="worker",
            model="anthropic/claude-sonnet-4-5-20250929",
            duration_ms=5000,
            project="test-project",
            spec_id="001-test",
            result="REVIEW",
        )
        assert entry.tokens_in == 1000
        assert entry.tokens_out == 500
        assert entry.cost_usd == 0.025
        assert entry.agent == "worker"
        assert entry.spec_id == "001-test"
        assert entry.duration_ms == 5000

    def test_missing_usage_defaults_to_zero(self) -> None:
        response = {}
        entry = AgentLogger.entry_from_litellm_response(
            response=response,
            agent="worker",
            model="test",
            duration_ms=100,
        )
        assert entry.tokens_in == 0
        assert entry.tokens_out == 0
        assert entry.cost_usd == 0.0

    def test_hidden_params_cost(self) -> None:
        response = {
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            "_hidden_params": {"response_cost": 0.01},
        }
        entry = AgentLogger.entry_from_litellm_response(
            response=response, agent="worker", model="test", duration_ms=100
        )
        assert entry.cost_usd == 0.01
