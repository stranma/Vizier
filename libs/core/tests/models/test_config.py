"""Tests for configuration models."""

from vizier.core.models.config import ModelTierConfig, ProjectConfig, ServerConfig


class TestModelTierConfig:
    def test_defaults(self) -> None:
        config = ModelTierConfig()
        assert "opus" in config.opus
        assert "sonnet" in config.sonnet
        assert "haiku" in config.haiku

    def test_custom_values(self) -> None:
        config = ModelTierConfig(opus="custom/opus", sonnet="custom/sonnet", haiku="custom/haiku")
        assert config.opus == "custom/opus"


class TestProjectConfig:
    def test_defaults(self) -> None:
        config = ProjectConfig()
        assert config.plugin == "software"
        assert config.model_tiers == {}

    def test_with_overrides(self) -> None:
        config = ProjectConfig(plugin="documents", model_tiers={"worker": "haiku", "architect": "opus"})
        assert config.plugin == "documents"
        assert config.model_tiers["worker"] == "haiku"


class TestServerConfig:
    def test_defaults(self) -> None:
        config = ServerConfig()
        assert isinstance(config.model_tiers, ModelTierConfig)
        assert config.reports_dir == "reports"
        assert config.reconciliation_interval_seconds == 60

    def test_custom_values(self) -> None:
        config = ServerConfig(reconciliation_interval_seconds=30, reports_dir="/opt/vizier/reports")
        assert config.reconciliation_interval_seconds == 30
        assert config.reports_dir == "/opt/vizier/reports"
