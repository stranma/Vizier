"""Composite secret store: chains multiple backends with priority ordering."""

from __future__ import annotations

from vizier.core.secrets.store import SecretStore  # noqa: TC001


class CompositeSecretStore:
    """Chains multiple SecretStore backends with priority ordering.

    Reads try each backend in order, returning the first hit.
    Writes go to the first backend that supports them.

    :param backends: Ordered list of secret store backends (highest priority first).
    """

    def __init__(self, backends: list[SecretStore]) -> None:
        if not backends:
            raise ValueError("CompositeSecretStore requires at least one backend")
        self._backends = list(backends)

    def get(self, key: str) -> str | None:
        """Retrieve a secret from the first backend that has it.

        :param key: Secret name.
        :returns: Secret value, or None if not found in any backend.
        """
        for backend in self._backends:
            val = backend.get(key)
            if val is not None:
                return val
        return None

    def has(self, key: str) -> bool:
        """Check whether any backend has this secret.

        :param key: Secret name.
        :returns: True if any backend has the key.
        """
        return any(backend.has(key) for backend in self._backends)

    def is_non_empty(self, key: str) -> bool:
        """Check whether the effective value (from get()) is non-empty.

        :param key: Secret name.
        :returns: True if get() would return a non-empty string.
        """
        val = self.get(key)
        return val is not None and len(val) > 0

    def keys(self) -> list[str]:
        """List all unique secret names across all backends.

        :returns: Sorted deduplicated list of secret key names.
        """
        all_keys: set[str] = set()
        for backend in self._backends:
            all_keys.update(backend.keys())
        return sorted(all_keys)

    def set(self, key: str, value: str) -> None:
        """Store a secret in the first writable backend.

        :param key: Secret name.
        :param value: Secret value.
        :raises NotImplementedError: If no backend supports writes.
        """
        for backend in self._backends:
            try:
                backend.set(key, value)
                return
            except NotImplementedError:
                continue
        raise NotImplementedError("No writable backend available")

    def delete(self, key: str) -> None:
        """Delete a secret from the first writable backend.

        :param key: Secret name.
        :raises NotImplementedError: If no backend supports deletes.
        """
        for backend in self._backends:
            try:
                backend.delete(key)
                return
            except NotImplementedError:
                continue
        raise NotImplementedError("No writable backend available")
