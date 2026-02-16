"""Environment file (.env) secret store backend for dev/CI fallback."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class EnvFileSecretStore:
    """Secret store backed by a .env file.

    Reads key=value pairs at initialization. Read-only after load:
    set() and delete() raise NotImplementedError.

    :param env_path: Path to .env file.
    """

    def __init__(self, env_path: str | Path) -> None:
        self._path = Path(env_path)
        self._cache: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Parse the .env file into the cache."""
        if not self._path.exists():
            logger.warning("Env file not found: %s", self._path)
            return

        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().upper()
            value = value.strip()
            if value and len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            self._cache[key] = value

        logger.info("Loaded %d secrets from %s", len(self._cache), self._path)

    def get(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        :param key: Secret name.
        :returns: Secret value, or None if not found.
        """
        return self._cache.get(key.upper())

    def has(self, key: str) -> bool:
        """Check whether a secret exists.

        :param key: Secret name.
        :returns: True if the key exists.
        """
        return key.upper() in self._cache

    def is_non_empty(self, key: str) -> bool:
        """Check whether a secret exists and has a non-empty value.

        :param key: Secret name.
        :returns: True if the key exists and value is non-empty.
        """
        val = self._cache.get(key.upper())
        return val is not None and len(val) > 0

    def keys(self) -> list[str]:
        """List all secret names (never values).

        :returns: Sorted list of secret key names.
        """
        return sorted(self._cache.keys())

    def set(self, key: str, value: str) -> None:
        """Not supported: .env store is read-only.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError("EnvFileSecretStore is read-only")

    def delete(self, key: str) -> None:
        """Not supported: .env store is read-only.

        :raises NotImplementedError: Always.
        """
        raise NotImplementedError("EnvFileSecretStore is read-only")
