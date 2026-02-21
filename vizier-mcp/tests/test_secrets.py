"""Tests for the secrets management module."""

from __future__ import annotations

from unittest.mock import patch

from vizier_mcp.secrets import get_secret


class TestGetSecret:
    def test_reads_from_env_var_when_no_vault(self) -> None:
        with patch.dict("os.environ", {"MY_SECRET": "env-value"}, clear=False):
            assert get_secret("MY_SECRET") == "env-value"

    def test_returns_none_when_not_set(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert get_secret("NONEXISTENT_VAR") is None

    def test_falls_back_to_env_when_vault_import_fails(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/", "MY_KEY": "fallback"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value=None),
        ):
            assert get_secret("MY_KEY") == "fallback"

    def test_reads_from_vault_when_configured(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value="vault-value") as mock_vault,
        ):
            result = get_secret("ANTHROPIC_API_KEY")
            assert result == "vault-value"
            mock_vault.assert_called_once_with("https://test.vault.azure.net/", "anthropic-api-key")

    def test_secret_name_mapping(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value="val") as mock_vault,
        ):
            get_secret("ANTHROPIC_API_KEY")
            mock_vault.assert_called_with("https://test.vault.azure.net/", "anthropic-api-key")

    def test_github_token_mapping(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value="ghp_test") as mock_vault,
        ):
            result = get_secret("GITHUB_TOKEN")
            assert result == "ghp_test"
            mock_vault.assert_called_with("https://test.vault.azure.net/", "github-pat")

    def test_unknown_key_uses_default_mapping(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value="val") as mock_vault,
        ):
            get_secret("SOME_OTHER_KEY")
            mock_vault.assert_called_with("https://test.vault.azure.net/", "some-other-key")


class TestReadFromVault:
    def test_returns_none_when_azure_not_installed(self) -> None:
        from vizier_mcp.secrets import _read_from_vault

        with patch.dict("sys.modules", {"azure.identity": None, "azure.keyvault.secrets": None}):
            result = _read_from_vault("https://test.vault.azure.net/", "my-secret")
            assert result is None

    def test_vault_reads_with_mocked_azure(self) -> None:
        env = {"AZURE_KEY_VAULT_URL": "https://test.vault.azure.net/"}
        with (
            patch.dict("os.environ", env, clear=False),
            patch("vizier_mcp.secrets._read_from_vault", return_value="vault-secret"),
        ):
            result = get_secret("ANTHROPIC_API_KEY")
            assert result == "vault-secret"
