"""Base worker abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vizier.core.models.spec import Spec


class BaseWorker(ABC):
    """Abstract base class for plugin workers.

    Workers execute specs: load context, call LLM, write artifacts.
    Each invocation is a fresh context (no state from previous runs).
    """

    @property
    @abstractmethod
    def allowed_tools(self) -> list[str]:
        """List of tool names this worker can use."""
        ...

    @property
    def tool_restrictions(self) -> dict[str, dict[str, list[str]]]:
        """Per-tool restriction patterns.

        :returns: Dict of tool_name -> {"allowed_patterns": [...], "denied_patterns": [...]}.
        """
        return {}

    @property
    def git_strategy(self) -> str:
        """Git strategy: 'branch_per_spec' or 'commit_to_main'."""
        return "branch_per_spec"

    @abstractmethod
    def get_prompt(self, spec: Spec, context: dict) -> str:
        """Render the worker prompt for a given spec.

        :param spec: The spec to implement.
        :param context: Project context (constitution, learnings, etc.).
        :returns: Rendered prompt string.
        """
        ...
