"""Base quality gate abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vizier.core.models.spec import Spec


class BaseQualityGate(ABC):
    """Abstract base class for plugin quality gates.

    Quality gates validate completed work through the 5-pass Completion Protocol.
    """

    @property
    @abstractmethod
    def automated_checks(self) -> list[dict[str, str]]:
        """List of automated checks to run.

        :returns: List of dicts with 'name' and 'command' keys.
        """
        ...

    @abstractmethod
    def get_prompt(self, spec: Spec, diff: str, context: dict) -> str:
        """Render the quality gate prompt for validation.

        :param spec: The spec being validated.
        :param diff: Git diff of the worker's changes.
        :param context: Project context.
        :returns: Rendered prompt string.
        """
        ...
