"""Secret check tool: agents can check secret existence without seeing values."""

from __future__ import annotations

from typing import Any

from vizier.core.secrets.store import SecretStore  # noqa: TC001


class SecretCheckTool:
    """Tool for agents to check secret metadata without accessing values.

    Agents can verify configuration by checking whether required secrets
    exist and have non-empty values, without ever seeing the actual secret.

    :param store: The secret store to check against.
    """

    TOOL_NAME = "check_secret"
    TOOL_DESCRIPTION = (
        "Check whether a secret is configured. Returns metadata (exists, has_value) but never the actual value. "
        "Use this to verify required credentials are available before attempting operations."
    )

    def __init__(self, store: SecretStore) -> None:
        self._store = store

    def check_secret(self, key: str) -> dict[str, Any]:
        """Check whether a secret exists and has a value.

        :param key: Secret name to check (e.g. GITHUB_TOKEN).
        :returns: Dict with exists and has_value booleans.
        """
        return {
            "key": key,
            "exists": self._store.has(key),
            "has_value": self._store.is_non_empty(key),
        }

    def list_configured_secrets(self) -> dict[str, Any]:
        """List all configured secret names.

        :returns: Dict with list of secret key names (never values).
        """
        keys = self._store.keys()
        return {
            "secrets": keys,
            "count": len(keys),
        }

    def execute(self, action: str, **kwargs: Any) -> dict[str, Any]:
        """Execute a secret check action.

        :param action: Either "check" or "list".
        :param kwargs: Additional arguments (key for check action).
        :returns: Action result.
        :raises ValueError: If action is unknown.
        """
        if action == "check":
            key = kwargs.get("key", "")
            if not key:
                raise ValueError("'key' argument required for check action")
            return self.check_secret(key)
        elif action == "list":
            return self.list_configured_secrets()
        else:
            raise ValueError(f"Unknown action: {action}. Supported: check, list")
