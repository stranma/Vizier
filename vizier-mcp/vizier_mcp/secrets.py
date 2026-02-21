"""Secret management with optional Azure Key Vault integration.

In production, reads secrets from Azure Key Vault when ``AZURE_KEY_VAULT_URL``
is set. Falls back to environment variables for local development.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_VAULT_URL_ENV = "AZURE_KEY_VAULT_URL"
_SECRET_MAPPING = {
    "ANTHROPIC_API_KEY": "anthropic-api-key",
}


def _read_from_vault(vault_url: str, secret_name: str) -> str | None:
    """Read a secret from Azure Key Vault.

    Requires ``azure-identity`` and ``azure-keyvault-secrets`` packages.
    Returns None if packages are unavailable or secret is not found.
    """
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore[import-untyped]
        from azure.keyvault.secrets import SecretClient  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("Azure Key Vault packages not installed; falling back to env vars")
        return None

    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        secret = client.get_secret(secret_name)
        return secret.value  # type: ignore[return-value]
    except Exception:
        logger.exception("Failed to read secret '%s' from Key Vault", secret_name)
        return None


def get_secret(env_var: str) -> str | None:
    """Get a secret value, trying Azure Key Vault first if configured.

    :param env_var: The environment variable name (e.g. ``ANTHROPIC_API_KEY``).
    :return: The secret value, or None if not found anywhere.
    """
    vault_url = os.environ.get(_VAULT_URL_ENV)

    if vault_url:
        kv_name = _SECRET_MAPPING.get(env_var, env_var.lower().replace("_", "-"))
        value = _read_from_vault(vault_url, kv_name)
        if value is not None:
            logger.info("Secret '%s' loaded from Azure Key Vault", env_var)
            return value
        logger.warning("Secret '%s' not in Key Vault; falling back to env var", env_var)

    return os.environ.get(env_var)
