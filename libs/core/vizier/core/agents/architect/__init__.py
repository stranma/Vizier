"""Architect agent: task decomposition with PROPOSE_PLAN and DAG dependencies."""

from vizier.core.agents.architect.factory import create_architect_runtime
from vizier.core.agents.architect.prompts import ArchitectPromptAssembler

__all__ = ["ArchitectPromptAssembler", "create_architect_runtime"]
