"""Rules-based model router (D3): resolution order is spec complexity > project config > plugin default > framework default."""

from __future__ import annotations

from vizier.core.models.config import ProjectConfig, ServerConfig
from vizier.core.models.spec import SpecComplexity

COMPLEXITY_TO_TIER: dict[SpecComplexity, str] = {
    SpecComplexity.LOW: "haiku",
    SpecComplexity.MEDIUM: "sonnet",
    SpecComplexity.HIGH: "opus",
}

ROLE_DEFAULTS: dict[str, str] = {
    "ea": "opus",
    "pasha": "opus",
    "architect": "opus",
    "worker": "sonnet",
    "quality_gate": "sonnet",
    "retrospective": "opus",
}


class ModelRouter:
    """Maps agent roles and spec complexity to concrete model identifiers.

    Resolution order (D3):
    1. Spec complexity field (worker only)
    2. Project config overrides
    3. Plugin default tiers
    4. Framework role defaults
    Then map tier name -> concrete model via server config.
    """

    def __init__(
        self,
        server_config: ServerConfig | None = None,
        project_config: ProjectConfig | None = None,
        plugin_defaults: dict[str, str] | None = None,
    ) -> None:
        self._server = server_config or ServerConfig()
        self._project = project_config or ProjectConfig()
        self._plugin_defaults = plugin_defaults or {}

    def resolve(
        self,
        role: str,
        spec_complexity: SpecComplexity | None = None,
    ) -> str:
        """Resolve a concrete model identifier for the given role.

        :param role: Agent role (e.g. "worker", "architect", "quality_gate").
        :param spec_complexity: Spec complexity (only applies to worker role).
        :returns: Concrete model string (e.g. "anthropic/claude-sonnet-4-5-20250929").
        """
        tier = self._resolve_tier(role, spec_complexity)
        return self._tier_to_model(tier)

    def _resolve_tier(self, role: str, spec_complexity: SpecComplexity | None) -> str:
        if role == "worker" and spec_complexity is not None:
            return COMPLEXITY_TO_TIER[spec_complexity]

        if role in self._project.model_tiers:
            return self._project.model_tiers[role]

        if role in self._plugin_defaults:
            return self._plugin_defaults[role]

        return ROLE_DEFAULTS.get(role, "sonnet")

    def _tier_to_model(self, tier: str) -> str:
        tiers = self._server.model_tiers
        mapping: dict[str, str] = {
            "opus": tiers.opus,
            "sonnet": tiers.sonnet,
            "haiku": tiers.haiku,
        }
        return mapping.get(tier, tiers.sonnet)
