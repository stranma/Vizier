"""Scout agent: LLM-based research triage with structured RESEARCH_REPORT output."""

from vizier.core.agents.scout.factory import create_scout_runtime
from vizier.core.agents.scout.prompts import ScoutPromptAssembler

__all__ = ["ScoutPromptAssembler", "create_scout_runtime"]
