"""Tests for AzureKeyVaultStore (all Azure calls mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from vizier.core.secrets.azure_store import AzureKeyVaultStore, _normalize_key, _to_azure_name


class TestKeyNormalization:
    def test_hyphens_to_underscores(self) -> None:
        assert _normalize_key("ANTHROPIC-API-KEY") == "ANTHROPIC_API_KEY"

    def test_uppercase(self) -> None:
        assert _normalize_key("my-key") == "MY_KEY"

    def test_already_normalized(self) -> None:
        assert _normalize_key("SIMPLE") == "SIMPLE"


class TestToAzureName:
    def test_underscores_to_hyphens(self) -> None:
        assert _to_azure_name("ANTHROPIC_API_KEY") == "ANTHROPIC-API-KEY"

    def test_uppercase(self) -> None:
        assert _to_azure_name("my_key") == "MY-KEY"


def _make_mock_client(secrets: dict[str, str], *, disabled: list[str] | None = None) -> MagicMock:
    """Build a mock SecretClient with the given secrets."""
    disabled_set = set(disabled or [])
    props = []
    for name in secrets:
        prop = SimpleNamespace(name=name, enabled=name not in disabled_set)
        props.append(prop)

    mock_client = MagicMock()
    mock_client.list_properties_of_secrets.return_value = props
    mock_client.get_secret.side_effect = lambda n: SimpleNamespace(value=secrets[n])
    return mock_client


def _make_azure_store(secrets: dict[str, str], *, disabled: list[str] | None = None) -> AzureKeyVaultStore:
    """Create an AzureKeyVaultStore with mocked Azure SDK."""
    mock_client = _make_mock_client(secrets, disabled=disabled)

    def fake_init_client(self: AzureKeyVaultStore, *_args: object, **_kwargs: object) -> None:
        self._client = mock_client  # type: ignore[attr-defined]

    with patch.object(AzureKeyVaultStore, "_init_client", fake_init_client):
        store = AzureKeyVaultStore(
            vault_url="https://test.vault.azure.net",
            tenant_id="tenant",
            client_id="client",
            client_secret="secret",
        )

    return store


class TestAzureKeyVaultStore:
    def test_get_existing_secret(self) -> None:
        store = _make_azure_store({"ANTHROPIC-API-KEY": "sk-test-123"})
        assert store.get("ANTHROPIC_API_KEY") == "sk-test-123"

    def test_get_missing_secret(self) -> None:
        store = _make_azure_store({"SOME-KEY": "value"})
        assert store.get("MISSING_KEY") is None

    def test_has_existing(self) -> None:
        store = _make_azure_store({"MY-SECRET": "val"})
        assert store.has("MY_SECRET")

    def test_has_missing(self) -> None:
        store = _make_azure_store({"MY-SECRET": "val"})
        assert not store.has("OTHER_SECRET")

    def test_is_non_empty(self) -> None:
        store = _make_azure_store({"FILLED": "val", "EMPTY-VAL": ""})
        assert store.is_non_empty("FILLED")
        assert not store.is_non_empty("EMPTY_VAL")
        assert not store.is_non_empty("MISSING")

    def test_keys_sorted_and_normalized(self) -> None:
        store = _make_azure_store({"ZEBRA-KEY": "z", "ALPHA-KEY": "a"})
        assert store.keys() == ["ALPHA_KEY", "ZEBRA_KEY"]

    def test_case_insensitive_get(self) -> None:
        store = _make_azure_store({"MY-KEY": "val"})
        assert store.get("my_key") == "val"
        assert store.get("MY_KEY") == "val"

    def test_set_updates_cache_and_calls_azure(self) -> None:
        store = _make_azure_store({"EXISTING": "old"})
        store._client.set_secret = MagicMock()

        store.set("NEW_KEY", "new_value")
        assert store.get("NEW_KEY") == "new_value"
        store._client.set_secret.assert_called_once_with("NEW-KEY", "new_value")

    def test_delete_removes_from_cache(self) -> None:
        store = _make_azure_store({"TO-DELETE": "val"})
        store._client.begin_delete_secret = MagicMock()

        store.delete("TO_DELETE")
        assert not store.has("TO_DELETE")
        store._client.begin_delete_secret.assert_called_once_with("TO-DELETE")

    def test_disabled_secrets_skipped(self) -> None:
        store = _make_azure_store({"ACTIVE": "val", "DISABLED": "skip"}, disabled=["DISABLED"])
        assert store.has("ACTIVE")
        assert not store.has("DISABLED")
