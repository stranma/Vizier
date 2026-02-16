"""SecretStore protocol: abstract interface for secret backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class SecretNotFoundError(KeyError):
    """Raised when a required secret is not found in any configured store."""


@runtime_checkable
class SecretStore(Protocol):
    """Protocol for secret storage backends.

    Implementations must provide read access (get, has, is_non_empty, keys)
    and optionally write access (set, delete). Read-only backends should
    raise NotImplementedError for set/delete.
    """

    def get(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        :param key: Secret name (e.g. ANTHROPIC_API_KEY).
        :returns: Secret value, or None if not found.
        """
        ...

    def has(self, key: str) -> bool:
        """Check whether a secret exists.

        :param key: Secret name.
        :returns: True if the key exists in the store.
        """
        ...

    def is_non_empty(self, key: str) -> bool:
        """Check whether a secret exists and has a non-empty value.

        :param key: Secret name.
        :returns: True if the key exists and value is non-empty.
        """
        ...

    def keys(self) -> list[str]:
        """List all secret names (never values).

        :returns: List of secret key names.
        """
        ...

    def set(self, key: str, value: str) -> None:
        """Store a secret value.

        :param key: Secret name.
        :param value: Secret value.
        :raises NotImplementedError: If the backend is read-only.
        """
        ...

    def delete(self, key: str) -> None:
        """Remove a secret.

        :param key: Secret name.
        :raises NotImplementedError: If the backend is read-only.
        """
        ...
