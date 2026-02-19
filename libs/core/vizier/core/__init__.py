"""Vizier core library."""

__version__ = "0.1.0"

from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.llm.factory import create_llm_callable
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
from vizier.core.plugins.discovery import discover_plugins, load_plugin, register_plugin
from vizier.core.plugins.templates import PromptTemplateRenderer
from vizier.core.plugins.tool_registry import ToolRegistry
from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig, BudgetTracker
from vizier.core.runtime.trace import TraceLogger
from vizier.core.runtime.types import RunResult, StopReason, ToolCallRecord, ToolDefinition
from vizier.core.secrets.composite_store import CompositeSecretStore
from vizier.core.secrets.store import SecretStore
from vizier.core.sentinel.content_scanner import ContentScanner, ContentScanResult, ContentVerdict
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest
from vizier.core.testing.vcr import VCRMode, VizierVCR
from vizier.core.tools.executor import ToolExecutor
from vizier.core.watcher.fs_watcher import FileSystemWatcher
from vizier.core.watcher.reconciler import Reconciler

__all__ = [
    "VALID_TRANSITIONS",
    "ActiveAgent",
    "AgentLogEntry",
    "AgentRuntime",
    "BasePlugin",
    "BudgetConfig",
    "BudgetTracker",
    "CompositeSecretStore",
    "ContentScanResult",
    "ContentScanner",
    "ContentVerdict",
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
    "RunResult",
    "SecretStore",
    "SentinelEngine",
    "SentinelResult",
    "ServerConfig",
    "Spec",
    "SpecComplexity",
    "SpecFrontmatter",
    "SpecStatus",
    "StateManager",
    "StopReason",
    "ToolCallRecord",
    "ToolCallRequest",
    "ToolDefinition",
    "ToolExecutor",
    "ToolRegistry",
    "TraceLogger",
    "VCRMode",
    "VizierVCR",
    "create_llm_callable",
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
