"""Plugin framework: base classes, discovery, templates, criteria, tool registry."""

from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.criteria_loader import CriteriaLibraryLoader
from vizier.core.plugins.discovery import discover_plugins, load_plugin, register_plugin
from vizier.core.plugins.templates import PromptTemplateRenderer
from vizier.core.plugins.tool_registry import ToolRegistry

__all__ = [
    "BasePlugin",
    "CriteriaLibraryLoader",
    "PromptTemplateRenderer",
    "ToolRegistry",
    "discover_plugins",
    "load_plugin",
    "register_plugin",
]
