"""Tests for model router resolution order (D3)."""

from vizier.core.model_router.router import ModelRouter
from vizier.core.models.config import ModelTierConfig, ProjectConfig, ServerConfig
from vizier.core.models.spec import SpecComplexity


class TestModelRouter:
    def test_framework_defaults(self) -> None:
        router = ModelRouter()
        assert "opus" in router.resolve("ea")
        assert "opus" in router.resolve("architect")
        assert "sonnet" in router.resolve("worker")
        assert "sonnet" in router.resolve("quality_gate")
        assert "opus" in router.resolve("retrospective")

    def test_spec_complexity_overrides_for_worker(self) -> None:
        router = ModelRouter()
        assert "haiku" in router.resolve("worker", spec_complexity=SpecComplexity.LOW)
        assert "sonnet" in router.resolve("worker", spec_complexity=SpecComplexity.MEDIUM)
        assert "opus" in router.resolve("worker", spec_complexity=SpecComplexity.HIGH)

    def test_spec_complexity_ignored_for_non_worker(self) -> None:
        router = ModelRouter()
        result = router.resolve("architect", spec_complexity=SpecComplexity.LOW)
        assert "opus" in result

    def test_project_config_overrides(self) -> None:
        project = ProjectConfig(model_tiers={"worker": "haiku", "architect": "sonnet"})
        router = ModelRouter(project_config=project)
        assert "haiku" in router.resolve("worker")
        assert "sonnet" in router.resolve("architect")

    def test_plugin_defaults_override_framework(self) -> None:
        plugin_defaults = {"worker": "opus", "quality_gate": "haiku"}
        router = ModelRouter(plugin_defaults=plugin_defaults)
        assert "opus" in router.resolve("worker")
        assert "haiku" in router.resolve("quality_gate")

    def test_resolution_order_spec_over_project(self) -> None:
        project = ProjectConfig(model_tiers={"worker": "opus"})
        router = ModelRouter(project_config=project)
        result = router.resolve("worker", spec_complexity=SpecComplexity.LOW)
        assert "haiku" in result

    def test_resolution_order_project_over_plugin(self) -> None:
        project = ProjectConfig(model_tiers={"worker": "haiku"})
        plugin_defaults = {"worker": "opus"}
        router = ModelRouter(project_config=project, plugin_defaults=plugin_defaults)
        result = router.resolve("worker")
        assert "haiku" in result

    def test_resolution_order_plugin_over_framework(self) -> None:
        plugin_defaults = {"worker": "opus"}
        router = ModelRouter(plugin_defaults=plugin_defaults)
        result = router.resolve("worker")
        assert "opus" in result

    def test_custom_server_models(self) -> None:
        server = ServerConfig(model_tiers=ModelTierConfig(opus="custom/opus-v2", sonnet="custom/sonnet-v2"))
        router = ModelRouter(server_config=server)
        assert router.resolve("ea") == "custom/opus-v2"
        assert router.resolve("worker") == "custom/sonnet-v2"

    def test_unknown_role_defaults_to_sonnet(self) -> None:
        router = ModelRouter()
        assert "sonnet" in router.resolve("unknown_role")
