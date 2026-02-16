"""Azure Key Vault secret store backend."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_key(azure_name: str) -> str:
    """Normalize Azure Key Vault name to Python env-var style.

    Azure Key Vault uses hyphens (ANTHROPIC-API-KEY);
    Python code expects underscores (ANTHROPIC_API_KEY).

    :param azure_name: Key name from Azure (may contain hyphens).
    :returns: Normalized key with underscores, uppercased.
    """
    return azure_name.upper().replace("-", "_")


def _to_azure_name(key: str) -> str:
    """Convert Python-style key to Azure Key Vault name.

    :param key: Python-style key (ANTHROPIC_API_KEY).
    :returns: Azure-style name (ANTHROPIC-API-KEY).
    """
    return key.upper().replace("_", "-")


class AzureKeyVaultStore:
    """Secret store backed by Azure Key Vault.

    Caches all secrets at initialization to avoid per-call network latency.
    Daemon restart picks up changes from Azure.

    :param vault_url: Azure Key Vault URL (e.g. https://myvault.vault.azure.net).
    :param tenant_id: Azure AD tenant ID.
    :param client_id: Service principal client ID.
    :param client_secret: Service principal client secret.
    """

    def __init__(self, vault_url: str, tenant_id: str, client_id: str, client_secret: str) -> None:
        self._vault_url = vault_url
        self._client: Any = None
        self._cache: dict[str, str] = {}
        self._init_client(tenant_id, client_id, client_secret)
        self._refresh()

    def _init_client(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        """Initialize the Azure SDK client."""
        from azure.identity import ClientSecretCredential
        from azure.keyvault.secrets import SecretClient

        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        self._client = SecretClient(vault_url=self._vault_url, credential=credential)

    def _refresh(self) -> None:
        """Fetch all secrets from Key Vault into local cache."""
        self._cache.clear()
        for prop in self._client.list_properties_of_secrets():
            if not prop.enabled:
                continue
            secret = self._client.get_secret(prop.name)
            key = _normalize_key(prop.name)
            self._cache[key] = secret.value or ""
        logger.info("Loaded %d secrets from Azure Key Vault", len(self._cache))

    def get(self, key: str) -> str | None:
        """Retrieve a secret value by key.

        :param key: Secret name (Python-style, e.g. ANTHROPIC_API_KEY).
        :returns: Secret value, or None if not found.
        """
        return self._cache.get(key.upper())

    def has(self, key: str) -> bool:
        """Check whether a secret exists.

        :param key: Secret name.
        :returns: True if the key exists in the cache.
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
        """Store a secret in Azure Key Vault and update cache.

        :param key: Secret name (Python-style).
        :param value: Secret value.
        """
        azure_name = _to_azure_name(key)
        self._client.set_secret(azure_name, value)
        self._cache[key.upper()] = value

    def delete(self, key: str) -> None:
        """Delete a secret from Azure Key Vault and remove from cache.

        :param key: Secret name (Python-style).
        """
        azure_name = _to_azure_name(key)
        self._client.begin_delete_secret(azure_name)
        self._cache.pop(key.upper(), None)
