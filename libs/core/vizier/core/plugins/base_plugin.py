"""Base plugin abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vizier.core.plugins.base_quality_gate import BaseQualityGate
    from vizier.core.plugins.base_worker import BaseWorker


class BasePlugin(ABC):
    """Abstract base class for Vizier plugins.

    Plugins define domain-specific behavior: worker class, quality gate class,
    default model tiers, architect guide, and criteria library.
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
    @abstractmethod
    def worker_class(self) -> type[BaseWorker]:
        """The worker class this plugin uses."""
        ...

    @property
    @abstractmethod
    def quality_gate_class(self) -> type[BaseQualityGate]:
        """The quality gate class this plugin uses."""
        ...

    @property
    def default_model_tiers(self) -> dict[str, str]:
        """Default model tier assignments for this plugin."""
        return {
            "worker": "sonnet",
            "quality_gate": "sonnet",
            "architect": "opus",
        }

    def get_architect_guide(self) -> str:
        """Return plugin-specific decomposition patterns guide.

        :returns: Markdown text for architect guidance.
        """
        return ""

    def get_criteria_library(self) -> dict[str, str]:
        """Return the criteria library: name -> full definition text.

        :returns: Dictionary mapping criteria names to their definitions.
        """
        return {}
