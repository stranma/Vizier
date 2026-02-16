"""LLM callable factory: creates closures that capture API keys from SecretStore."""

from __future__ import annotations

from typing import Any

from vizier.core.secrets.store import SecretNotFoundError, SecretStore

PROVIDER_KEY_MAP: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "azure": "AZURE_API_KEY",
}

LLMCallable = Any


def create_llm_callable(secret_store: SecretStore, provider: str = "anthropic") -> LLMCallable:
    """Create an LLM callable closure that captures the API key from the secret store.

    The API key is captured in the closure scope -- never in os.environ,
    never passed through agent context.

    :param secret_store: Secret store to retrieve the API key from.
    :param provider: LLM provider name (maps to key name via PROVIDER_KEY_MAP).
    :returns: A callable compatible with litellm.completion.
    :raises SecretNotFoundError: If the API key is not found in the store.
    """
    key_name = PROVIDER_KEY_MAP.get(provider)
    if key_name is None:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: {sorted(PROVIDER_KEY_MAP.keys())}")

    api_key = secret_store.get(key_name)
    if not api_key:
        raise SecretNotFoundError(
            f"{key_name} not found in secret store. Configure it in Azure Key Vault or .env file."
        )

    def llm_callable(**kwargs: Any) -> Any:
        """Call litellm.completion with the captured API key."""
        import litellm

        return litellm.completion(api_key=api_key, **kwargs)

    return llm_callable
