"""Tests for plugin discovery and registration."""

import pytest

from tests.plugins.conftest import StubPlugin
from vizier.core.plugins.discovery import clear_registry, discover_plugins, load_plugin, register_plugin


@pytest.fixture(autouse=True)
def _clean_registry():
    yield
    clear_registry()


class TestPluginDiscovery:
    def test_programmatic_registration(self) -> None:
        register_plugin("stub", StubPlugin)
        plugins = discover_plugins()
        assert "stub" in plugins
        assert plugins["stub"].name == "stub"

    def test_load_registered_plugin(self) -> None:
        register_plugin("stub", StubPlugin)
        plugin = load_plugin("stub")
        assert plugin is not None
        assert plugin.name == "stub"

    def test_load_nonexistent_returns_none(self) -> None:
        assert load_plugin("nonexistent") is None

    def test_discover_with_no_plugins(self) -> None:
        plugins = discover_plugins()
        assert isinstance(plugins, dict)

    def test_clear_registry(self) -> None:
        register_plugin("stub", StubPlugin)
        clear_registry()
        plugin = load_plugin("stub")
        assert plugin is None
