"""Tests for orchestration Pydantic models (PingMessage, PingUrgency, ProjectConfig)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vizier_mcp.models.orchestration import PingMessage, PingUrgency, ProjectConfig


class TestPingUrgency:
    """Tests for PingUrgency enum (AC-O6)."""

    def test_has_exactly_three_values(self) -> None:
        assert len(PingUrgency) == 3

    def test_question_value(self) -> None:
        assert PingUrgency.QUESTION == "QUESTION"

    def test_blocker_value(self) -> None:
        assert PingUrgency.BLOCKER == "BLOCKER"

    def test_impossible_value(self) -> None:
        assert PingUrgency.IMPOSSIBLE == "IMPOSSIBLE"

    def test_values_are_strings(self) -> None:
        for urgency in PingUrgency:
            assert isinstance(urgency, str)


class TestPingMessage:
    """Tests for PingMessage model (AC-O6)."""

    def test_valid_ping(self) -> None:
        ping = PingMessage(spec_id="001-auth", urgency=PingUrgency.QUESTION, message="How to handle OAuth?")
        assert ping.spec_id == "001-auth"
        assert ping.urgency == PingUrgency.QUESTION
        assert ping.message == "How to handle OAuth?"
        assert isinstance(ping.created_at, datetime)

    def test_urgency_from_string(self) -> None:
        ping = PingMessage(spec_id="001-auth", urgency="BLOCKER", message="blocked")
        assert ping.urgency == PingUrgency.BLOCKER

    def test_invalid_urgency_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PingMessage(spec_id="001-auth", urgency="CRITICAL", message="not valid")

    def test_created_at_default(self) -> None:
        before = datetime.now(UTC)
        ping = PingMessage(spec_id="001-auth", urgency=PingUrgency.QUESTION, message="test")
        after = datetime.now(UTC)
        assert before <= ping.created_at <= after

    def test_custom_created_at(self) -> None:
        ts = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        ping = PingMessage(spec_id="001-auth", urgency=PingUrgency.BLOCKER, message="test", created_at=ts)
        assert ping.created_at == ts

    def test_all_urgency_values_accepted(self) -> None:
        for urgency in PingUrgency:
            ping = PingMessage(spec_id="001-test", urgency=urgency, message="test")
            assert ping.urgency == urgency

    def test_json_roundtrip(self) -> None:
        ping = PingMessage(spec_id="001-auth", urgency=PingUrgency.IMPOSSIBLE, message="spec contradicts itself")
        data = ping.model_dump_json()
        restored = PingMessage.model_validate_json(data)
        assert restored.spec_id == ping.spec_id
        assert restored.urgency == ping.urgency
        assert restored.message == ping.message

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            PingMessage(spec_id="001-auth")  # type: ignore[call-arg]


class TestProjectConfig:
    """Tests for ProjectConfig model."""

    def test_default_values(self) -> None:
        config = ProjectConfig()
        assert config.type is None
        assert config.language is None
        assert config.framework is None
        assert config.test_command is None
        assert config.lint_command is None
        assert config.type_command is None
        assert config.settings == {}

    def test_full_config(self) -> None:
        config = ProjectConfig(
            type="software",
            language="python",
            framework="fastapi",
            test_command="pytest",
            lint_command="ruff check .",
            type_command="pyright",
            settings={"coverage_threshold": 80},
        )
        assert config.type == "software"
        assert config.language == "python"
        assert config.settings["coverage_threshold"] == 80

    def test_partial_config(self) -> None:
        config = ProjectConfig(type="documents")
        assert config.type == "documents"
        assert config.language is None
        assert config.settings == {}

    def test_dict_roundtrip(self) -> None:
        config = ProjectConfig(type="software", language="python", settings={"key": "value"})
        data = config.model_dump()
        restored = ProjectConfig(**data)
        assert restored.type == config.type
        assert restored.settings == config.settings
