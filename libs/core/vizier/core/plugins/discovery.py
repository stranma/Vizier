"""Plugin discovery via entry points and programmatic registration."""

from __future__ import annotations

from importlib.metadata import entry_points
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vizier.core.plugins.base_plugin import BasePlugin

_REGISTRY: dict[str, type[BasePlugin]] = {}


def discover_plugins() -> dict[str, BasePlugin]:
    """Discover installed plugins via entry points.

    Scans the 'vizier.plugins' entry point group and instantiates each plugin.

    :returns: Dict of plugin_name -> plugin_instance.
    """
    plugins: dict[str, BasePlugin] = {}
    group = entry_points(group="vizier.plugins")
    for ep in group:
        try:
            plugin_class = ep.load()
            plugins[ep.name] = plugin_class()
        except Exception:
            pass

    for name, cls in _REGISTRY.items():
        if name not in plugins:
            plugins[name] = cls()

    return plugins


def load_plugin(name: str) -> BasePlugin | None:
    """Load a single plugin by name.

    :param name: Plugin name to look for.
    :returns: Plugin instance, or None if not found.
    """
    plugins = discover_plugins()
    return plugins.get(name)


def register_plugin(name: str, plugin_class: type[BasePlugin]) -> None:
    """Programmatically register a plugin (for testing).

    :param name: Plugin name.
    :param plugin_class: Plugin class to register.
    """
    _REGISTRY[name] = plugin_class


def clear_registry() -> None:
    """Clear the programmatic plugin registry (for test cleanup)."""
    _REGISTRY.clear()
