"""Agent context: immutable, loaded from disk per invocation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from vizier.core.file_protocol.spec_io import read_spec

if TYPE_CHECKING:
    from vizier.core.models.spec import Spec


class AgentContext:
    """Immutable context loaded from disk for a single agent invocation.

    Enforces the fresh-context pattern: every agent loads state from disk,
    never from in-memory state carried over from a previous invocation.

    :param project_root: Root directory of the project.
    :param spec: The spec being processed (if applicable).
    :param constitution: Project constitution text.
    :param learnings: Project learnings text.
    :param config: Parsed project config.
    """

    def __init__(
        self,
        project_root: str,
        spec: Spec | None = None,
        constitution: str = "",
        learnings: str = "",
        config: dict[str, Any] | None = None,
    ) -> None:
        self._project_root = project_root
        self._spec = spec
        self._constitution = constitution
        self._learnings = learnings
        self._config = config or {}

    @property
    def project_root(self) -> str:
        return self._project_root

    @property
    def spec(self) -> Spec | None:
        return self._spec

    @property
    def constitution(self) -> str:
        return self._constitution

    @property
    def learnings(self) -> str:
        return self._learnings

    @property
    def config(self) -> dict[str, Any]:
        return self._config

    @classmethod
    def load_from_disk(cls, project_root: str | Path, spec_path: str | None = None) -> AgentContext:
        """Load a fresh context entirely from disk.

        :param project_root: Root directory of the project.
        :param spec_path: Path to the spec.md file (optional).
        :returns: Freshly loaded AgentContext.
        """
        root = Path(project_root)
        vizier_dir = root / ".vizier"

        spec: Spec | None = None
        if spec_path:
            spec = read_spec(spec_path)

        constitution = ""
        constitution_path = vizier_dir / "constitution.md"
        if constitution_path.exists():
            constitution = constitution_path.read_text(encoding="utf-8")

        learnings = ""
        learnings_path = vizier_dir / "learnings.md"
        if learnings_path.exists():
            learnings = learnings_path.read_text(encoding="utf-8")

        config: dict[str, Any] = {}
        config_path = vizier_dir / "config.yaml"
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        return cls(
            project_root=str(root),
            spec=spec,
            constitution=constitution,
            learnings=learnings,
            config=config,
        )

    def as_dict(self) -> dict[str, Any]:
        """Convert context to a dict for template rendering.

        :returns: Dict with context fields.
        """
        return {
            "project_root": self._project_root,
            "constitution": self._constitution,
            "learnings": self._learnings,
            "config": self._config,
        }
