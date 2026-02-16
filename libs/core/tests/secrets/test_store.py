"""Tests for SecretStore protocol."""

from vizier.core.secrets.store import SecretNotFoundError, SecretStore


class TestSecretStoreProtocol:
    def test_secret_not_found_error_is_key_error(self) -> None:
        err = SecretNotFoundError("MISSING_KEY")
        assert isinstance(err, KeyError)

    def test_env_file_store_is_secret_store(self) -> None:
        from vizier.core.secrets.env_file_store import EnvFileSecretStore

        assert issubclass(EnvFileSecretStore, SecretStore)

    def test_composite_store_is_secret_store(self) -> None:
        from vizier.core.secrets.composite_store import CompositeSecretStore

        assert issubclass(CompositeSecretStore, SecretStore)

    def test_azure_store_is_secret_store(self) -> None:
        from vizier.core.secrets.azure_store import AzureKeyVaultStore

        assert issubclass(AzureKeyVaultStore, SecretStore)
