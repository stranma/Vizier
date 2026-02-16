"""Vizier core library."""

__version__ = "0.1.0"

from vizier.core.agent.base import BaseAgent
from vizier.core.agent.context import AgentContext
from vizier.core.agent_runner.runner import AgentRunner, RunResult
from vizier.core.architect.decomposition import SubSpecDefinition, estimate_complexity, parse_decomposition
from vizier.core.architect.runtime import ArchitectRuntime
from vizier.core.ea.budget import BudgetEnforcer, BudgetStatus, BudgetThreshold
from vizier.core.ea.classifier import MessageCategory, MessageClassifier, PromptModule
from vizier.core.ea.models import (
    BriefingConfig,
    BudgetConfig,
    CheckinRecord,
    CheckoutRecord,
    Commitment,
    CommitmentStatus,
    FocusMode,
    PrioritiesConfig,
    Priority,
    PriorityLevel,
    Relationship,
)
from vizier.core.ea.prompt_assembly import PromptAssembler
from vizier.core.ea.runtime import EARuntime
from vizier.core.ea.tracking import CommitmentTracker, RelationshipTracker
from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.lifecycle.retry import GraduatedRetry, RetryAction, RetryThreshold
from vizier.core.lifecycle.spec_lifecycle import SpecLifecycle
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
from vizier.core.pasha.orchestrator import PashaOrchestrator
from vizier.core.pasha.progress import CycleReport, ProgressReporter, ProjectStatus
from vizier.core.pasha.subprocess_manager import AgentProcess, SubprocessManager
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.discovery import discover_plugins, load_plugin, register_plugin
from vizier.core.plugins.templates import PromptTemplateRenderer
from vizier.core.plugins.tool_registry import ToolRegistry
from vizier.core.quality_gate.runtime import QualityGateRuntime
from vizier.core.retrospective.analysis import FailurePattern, RetrospectiveAnalysis, SpecMetrics
from vizier.core.retrospective.runtime import RetrospectiveRuntime
from vizier.core.sentinel.content_scanner import ContentScanner, ContentScanResult, ContentVerdict
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest
from vizier.core.testing.vcr import VCRMode, VizierVCR
from vizier.core.watcher.fs_watcher import FileSystemWatcher
from vizier.core.watcher.reconciler import Reconciler
from vizier.core.worker.runtime import WorkerRuntime

__all__ = [
    "VALID_TRANSITIONS",
    "ActiveAgent",
    "AgentContext",
    "AgentLogEntry",
    "AgentLogger",
    "AgentProcess",
    "AgentRunner",
    "ArchitectRuntime",
    "BaseAgent",
    "BasePlugin",
    "BaseQualityGate",
    "BaseWorker",
    "BriefingConfig",
    "BudgetConfig",
    "BudgetEnforcer",
    "BudgetStatus",
    "BudgetThreshold",
    "CheckinRecord",
    "CheckoutRecord",
    "Commitment",
    "CommitmentStatus",
    "CommitmentTracker",
    "ContentScanResult",
    "ContentScanner",
    "ContentVerdict",
    "CycleReport",
    "EARuntime",
    "EventType",
    "FailurePattern",
    "FileEvent",
    "FileSystemWatcher",
    "FocusMode",
    "GraduatedRetry",
    "MessageCategory",
    "MessageClassifier",
    "ModelRouter",
    "ModelTierConfig",
    "PashaOrchestrator",
    "PolicyDecision",
    "PrioritiesConfig",
    "Priority",
    "PriorityLevel",
    "ProgressReporter",
    "ProjectConfig",
    "ProjectState",
    "ProjectStatus",
    "PromptAssembler",
    "PromptModule",
    "PromptTemplateRenderer",
    "QualityGateRuntime",
    "Reconciler",
    "Relationship",
    "RelationshipTracker",
    "RetrospectiveAnalysis",
    "RetrospectiveRuntime",
    "RetryAction",
    "RetryThreshold",
    "RunResult",
    "SentinelEngine",
    "SentinelResult",
    "ServerConfig",
    "Spec",
    "SpecComplexity",
    "SpecFrontmatter",
    "SpecLifecycle",
    "SpecMetrics",
    "SpecStatus",
    "StateManager",
    "SubSpecDefinition",
    "SubprocessManager",
    "ToolCallRequest",
    "ToolRegistry",
    "VCRMode",
    "VizierVCR",
    "WorkerRuntime",
    "create_spec",
    "discover_plugins",
    "estimate_complexity",
    "list_specs",
    "load_plugin",
    "parse_decomposition",
    "read_spec",
    "register_plugin",
    "resolve_criteria_references",
    "snapshot_criteria",
    "update_spec_status",
]
