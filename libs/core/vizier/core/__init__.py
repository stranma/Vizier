"""Vizier core library."""

__version__ = "0.1.0"

from vizier.core.agent.base import BaseAgent
from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.model_router.router import ModelRouter
from vizier.core.models import (
    VALID_TRANSITIONS,
    ActiveAgent,
    AgentLogEntry,
    EventType,
    FileEvent,
    ModelTierConfig,
    ProjectConfig,
    ProjectState,
    ServerConfig,
    Spec,
    SpecComplexity,
    SpecFrontmatter,
    SpecStatus,
)
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.discovery import discover_plugins, load_plugin, register_plugin
from vizier.core.plugins.templates import PromptTemplateRenderer
from vizier.core.plugins.tool_registry import ToolRegistry
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest
from vizier.core.watcher.fs_watcher import FileSystemWatcher
from vizier.core.watcher.reconciler import Reconciler

__all__ = [
    "VALID_TRANSITIONS",
    "ActiveAgent",
    "AgentContext",
    "AgentLogEntry",
    "AgentLogger",
    "BaseAgent",
    "BasePlugin",
    "BaseQualityGate",
    "BaseWorker",
    "EventType",
    "FileEvent",
    "FileSystemWatcher",
    "ModelRouter",
    "ModelTierConfig",
    "PolicyDecision",
    "ProjectConfig",
    "ProjectState",
    "PromptTemplateRenderer",
    "Reconciler",
    "SentinelEngine",
    "SentinelResult",
    "ServerConfig",
    "Spec",
    "SpecComplexity",
    "SpecFrontmatter",
    "SpecStatus",
    "StateManager",
    "ToolCallRequest",
    "ToolRegistry",
    "create_spec",
    "discover_plugins",
    "list_specs",
    "load_plugin",
    "read_spec",
    "register_plugin",
    "resolve_criteria_references",
    "snapshot_criteria",
    "update_spec_status",
]
