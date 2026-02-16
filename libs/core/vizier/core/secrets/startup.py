"""Secret store startup helpers: factory creation and environment sanitization."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from vizier.core.secrets.composite_store import CompositeSecretStore
from vizier.core.secrets.env_file_store import EnvFileSecretStore
from vizier.core.secrets.store import SecretStore  # noqa: TC001

logger = logging.getLogger(__name__)

BOOTSTRAP_KEYS = frozenset(
    {
        "AZURE_TENANT_ID",
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET",
    }
)

SENSITIVE_PATTERNS = frozenset(
    {
        "KEY",
        "TOKEN",
        "SECRET",
        "PASSWORD",
        "CREDENTIAL",
    }
)


def create_secret_store(
    vizier_root: str,
    *,
    azure_vault_url: str = "",
    azure_tenant_id: str = "",
    azure_client_id: str = "",
    azure_client_secret: str = "",
) -> SecretStore:
    """Create a composite secret store with Azure primary + .env fallback.

    :param vizier_root: Vizier root directory.
    :param azure_vault_url: Azure Key Vault URL (optional).
    :param azure_tenant_id: Azure AD tenant ID (optional).
    :param azure_client_id: Service principal client ID (optional).
    :param azure_client_secret: Service principal client secret (optional).
    :returns: Configured secret store (composite or env-file-only).
    """
    backends: list[Any] = []

    if azure_vault_url and azure_tenant_id and azure_client_id and azure_client_secret:
        try:
            from vizier.core.secrets.azure_store import AzureKeyVaultStore

            azure_store = AzureKeyVaultStore(
                vault_url=azure_vault_url,
                tenant_id=azure_tenant_id,
                client_id=azure_client_id,
                client_secret=azure_client_secret,
            )
            backends.append(azure_store)
            logger.info("Azure Key Vault backend initialized: %s", azure_vault_url)
        except Exception:
            logger.exception("Failed to initialize Azure Key Vault backend")

    env_path = Path(vizier_root) / ".env"
    if env_path.exists():
        env_store = EnvFileSecretStore(env_path)
        backends.append(env_store)
        logger.info("Env file backend initialized: %s", env_path)

    bootstrap_path = Path(vizier_root) / ".env.bootstrap"
    if bootstrap_path.exists():
        bootstrap_store = EnvFileSecretStore(bootstrap_path)
        backends.append(bootstrap_store)
        logger.info("Bootstrap file backend initialized: %s", bootstrap_path)

    if not backends:
        logger.warning("No secret backends configured, using empty env-file store")
        return EnvFileSecretStore(env_path)

    if len(backends) == 1:
        return backends[0]

    return CompositeSecretStore(backends)


def load_bootstrap_credentials(vizier_root: str) -> dict[str, str]:
    """Load Azure bootstrap credentials from .env.bootstrap or os.environ.

    Checks .env.bootstrap first, then falls back to os.environ for each key.

    :param vizier_root: Vizier root directory.
    :returns: Dict with azure_tenant_id, azure_client_id, azure_client_secret keys.
    """
    bootstrap_path = Path(vizier_root) / ".env.bootstrap"
    bootstrap_store: EnvFileSecretStore | None = None
    if bootstrap_path.exists():
        bootstrap_store = EnvFileSecretStore(bootstrap_path)

    result: dict[str, str] = {}
    for key in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        value = ""
        if bootstrap_store:
            value = bootstrap_store.get(key) or ""
        if not value:
            value = os.environ.get(key, "")
        result[key.lower()] = value

    return result


def sanitize_environment(known_secret_keys: list[str]) -> list[str]:
    """Remove sensitive environment variables from os.environ.

    Removes bootstrap keys + any keys matching sensitive patterns + explicitly
    known secret keys. Defense-in-depth against env-reading attacks.

    :param known_secret_keys: Secret key names from the store.
    :returns: List of removed variable names.
    """
    removed: list[str] = []
    keys_to_check = set(known_secret_keys) | BOOTSTRAP_KEYS

    for key in list(os.environ.keys()):
        upper_key = key.upper()
        should_remove = upper_key in keys_to_check or any(p in upper_key for p in SENSITIVE_PATTERNS)
        if should_remove:
            os.environ.pop(key, None)
            removed.append(key)

    if removed:
        logger.info("Sanitized %d environment variables: %s", len(removed), ", ".join(sorted(removed)))

    return removed
