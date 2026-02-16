"""Tests for secret store startup helpers."""

from __future__ import annotations

import os
from pathlib import Path  # noqa: TC003

from vizier.core.secrets.env_file_store import EnvFileSecretStore
from vizier.core.secrets.startup import (
    create_secret_store,
    load_bootstrap_credentials,
    sanitize_environment,
)


class TestCreateSecretStore:
    def test_env_file_only(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("MY_KEY=val\n")

        store = create_secret_store(str(tmp_path))
        assert isinstance(store, EnvFileSecretStore)
        assert store.get("MY_KEY") == "val"

    def test_empty_when_no_files(self, tmp_path: Path) -> None:
        store = create_secret_store(str(tmp_path))
        assert store.keys() == []

    def test_bootstrap_file_included(self, tmp_path: Path) -> None:
        bootstrap = tmp_path / ".env.bootstrap"
        bootstrap.write_text("AZURE_TENANT_ID=tid\n")

        store = create_secret_store(str(tmp_path))
        assert store.get("AZURE_TENANT_ID") == "tid"

    def test_env_and_bootstrap_combined(self, tmp_path: Path) -> None:
        env = tmp_path / ".env"
        env.write_text("APP_KEY=app\n")
        bootstrap = tmp_path / ".env.bootstrap"
        bootstrap.write_text("AZURE_TENANT_ID=tid\n")

        store = create_secret_store(str(tmp_path))
        assert store.get("APP_KEY") == "app"
        assert store.get("AZURE_TENANT_ID") == "tid"


class TestLoadBootstrapCredentials:
    def test_from_bootstrap_file(self, tmp_path: Path) -> None:
        bootstrap = tmp_path / ".env.bootstrap"
        bootstrap.write_text("AZURE_TENANT_ID=tid\nAZURE_CLIENT_ID=cid\nAZURE_CLIENT_SECRET=csec\n")

        creds = load_bootstrap_credentials(str(tmp_path))
        assert creds["azure_tenant_id"] == "tid"
        assert creds["azure_client_id"] == "cid"
        assert creds["azure_client_secret"] == "csec"

    def test_fallback_to_environ(self, tmp_path: Path, monkeypatch: object) -> None:
        import pytest

        mp = pytest.MonkeyPatch()
        mp.setenv("AZURE_TENANT_ID", "env_tid")
        mp.setenv("AZURE_CLIENT_ID", "env_cid")
        mp.setenv("AZURE_CLIENT_SECRET", "env_csec")
        try:
            creds = load_bootstrap_credentials(str(tmp_path))
            assert creds["azure_tenant_id"] == "env_tid"
            assert creds["azure_client_id"] == "env_cid"
            assert creds["azure_client_secret"] == "env_csec"
        finally:
            mp.undo()

    def test_empty_when_nothing_configured(self, tmp_path: Path) -> None:
        creds = load_bootstrap_credentials(str(tmp_path))
        assert creds["azure_tenant_id"] == ""
        assert creds["azure_client_id"] == ""
        assert creds["azure_client_secret"] == ""


class TestSanitizeEnvironment:
    def test_removes_known_keys(self) -> None:
        os.environ["TEST_SANITIZE_KEY"] = "val"
        try:
            removed = sanitize_environment(["TEST_SANITIZE_KEY"])
            assert "TEST_SANITIZE_KEY" in removed
            assert "TEST_SANITIZE_KEY" not in os.environ
        finally:
            os.environ.pop("TEST_SANITIZE_KEY", None)

    def test_removes_bootstrap_keys(self) -> None:
        os.environ["AZURE_TENANT_ID"] = "tid"
        os.environ["AZURE_CLIENT_ID"] = "cid"
        os.environ["AZURE_CLIENT_SECRET"] = "csec"
        try:
            removed = sanitize_environment([])
            assert "AZURE_TENANT_ID" in removed
            assert "AZURE_CLIENT_ID" in removed
            assert "AZURE_CLIENT_SECRET" in removed
        finally:
            for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
                os.environ.pop(k, None)

    def test_removes_sensitive_pattern_keys(self) -> None:
        os.environ["MY_API_TOKEN"] = "tok"
        os.environ["DB_PASSWORD"] = "pw"
        try:
            removed = sanitize_environment([])
            assert "MY_API_TOKEN" in removed
            assert "DB_PASSWORD" in removed
        finally:
            os.environ.pop("MY_API_TOKEN", None)
            os.environ.pop("DB_PASSWORD", None)

    def test_does_not_remove_safe_keys(self) -> None:
        os.environ["PATH_BACKUP_TEST"] = "safe"
        try:
            removed = sanitize_environment([])
            assert "PATH_BACKUP_TEST" not in removed
            assert os.environ.get("PATH_BACKUP_TEST") == "safe"
        finally:
            os.environ.pop("PATH_BACKUP_TEST", None)

    def test_returns_removed_list(self) -> None:
        os.environ["REMOVE_ME_TOKEN"] = "val"
        try:
            removed = sanitize_environment(["EXTRA_KEY"])
            assert isinstance(removed, list)
        finally:
            os.environ.pop("REMOVE_ME_TOKEN", None)
