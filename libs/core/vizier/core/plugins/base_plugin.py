"""Base plugin abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BasePlugin(ABC):
    """Abstract base class for Vizier plugins.

    Plugins define domain-specific behavior: write-set patterns, required evidence,
    system prompt guides, model tiers, and criteria library.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin identifier (e.g. 'software', 'documents')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable plugin description."""
        ...

    @property
    def worker_write_set(self) -> list[str]:
        """Glob patterns defining where Worker can write (D55).

        :returns: List of glob patterns (e.g. ``["src/**/*.py", "tests/**"]``).
        """
        return []

    @property
    def required_evidence(self) -> list[str]:
        """Evidence types required for DONE transition (D56).

        :returns: List of evidence type names (e.g. ``["test_output", "lint_output"]``).
        """
        return []

    @property
    def system_prompts(self) -> dict[str, str]:
        """Per-role system prompt guides injected into agent prompts.

        :returns: Dict mapping role names to prompt guide text.
        """
        return {}

    @property
    def tool_overrides(self) -> dict[str, dict[str, list[str]]]:
        """Per-tool restriction overrides for this plugin.

        :returns: Dict mapping tool names to restriction dicts with
                  ``allowed_patterns`` and ``denied_patterns`` keys.
        """
        return {}

    @property
    def default_model_tiers(self) -> dict[str, str]:
        """Default model tier assignments for this plugin."""
        return {
            "worker": "sonnet",
            "quality_gate": "sonnet",
            "architect": "opus",
            "scout": "sonnet",
        }

    def get_scout_guide(self) -> str:
        """Return plugin-specific research guidance for the Scout agent.

        :returns: Markdown text for scout research guidance.
        """
        return self.system_prompts.get("scout", "")

    def get_architect_guide(self) -> str:
        """Return plugin-specific decomposition patterns guide.

        :returns: Markdown text for architect guidance.
        """
        return self.system_prompts.get("architect", "")

    def get_worker_guide(self) -> str:
        """Return plugin-specific worker execution guidance.

        :returns: Markdown text for worker guidance.
        """
        return self.system_prompts.get("worker", "")

    def get_quality_gate_guide(self) -> str:
        """Return plugin-specific quality gate guidance.

        :returns: Markdown text for quality gate guidance.
        """
        return self.system_prompts.get("quality_gate", "")

    def get_criteria_library(self) -> dict[str, str]:
        """Return the criteria library: name -> full definition text.

        :returns: Dictionary mapping criteria names to their definitions.
        """
        return {}
