"""Tests for EnvFileSecretStore."""

from pathlib import Path

import pytest

from vizier.core.secrets.env_file_store import EnvFileSecretStore


class TestEnvFileSecretStore:
    def test_load_simple_values(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=sk-123\nDB_HOST=localhost\n")

        store = EnvFileSecretStore(env_file)
        assert store.get("API_KEY") == "sk-123"
        assert store.get("DB_HOST") == "localhost"

    def test_keys_uppercase_normalized(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("my_key=value\n")

        store = EnvFileSecretStore(env_file)
        assert store.has("MY_KEY")
        assert store.get("my_key") == "value"

    def test_skips_comments_and_blanks(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=val\n  # another\n")

        store = EnvFileSecretStore(env_file)
        assert store.keys() == ["KEY"]

    def test_skips_lines_without_equals(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("NOEQUALS\nKEY=val\n")

        store = EnvFileSecretStore(env_file)
        assert store.keys() == ["KEY"]

    def test_strips_quotes(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("DOUBLE=\"hello\"\nSINGLE='world'\n")

        store = EnvFileSecretStore(env_file)
        assert store.get("DOUBLE") == "hello"
        assert store.get("SINGLE") == "world"

    def test_has_returns_false_for_missing(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")

        store = EnvFileSecretStore(env_file)
        assert not store.has("MISSING")

    def test_is_non_empty(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FILLED=value\nEMPTY=\n")

        store = EnvFileSecretStore(env_file)
        assert store.is_non_empty("FILLED")
        assert not store.is_non_empty("EMPTY")
        assert not store.is_non_empty("MISSING")

    def test_keys_returns_sorted(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("ZEBRA=z\nAPPLE=a\nMIDDLE=m\n")

        store = EnvFileSecretStore(env_file)
        assert store.keys() == ["APPLE", "MIDDLE", "ZEBRA"]

    def test_set_raises_not_implemented(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")

        store = EnvFileSecretStore(env_file)
        with pytest.raises(NotImplementedError, match="read-only"):
            store.set("NEW", "value")

    def test_delete_raises_not_implemented(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val\n")

        store = EnvFileSecretStore(env_file)
        with pytest.raises(NotImplementedError, match="read-only"):
            store.delete("KEY")

    def test_missing_file_creates_empty_store(self, tmp_path: Path) -> None:
        store = EnvFileSecretStore(tmp_path / "nonexistent.env")
        assert store.keys() == []
        assert store.get("ANYTHING") is None

    def test_value_with_equals_sign(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("CONNECTION=host=localhost;port=5432\n")

        store = EnvFileSecretStore(env_file)
        assert store.get("CONNECTION") == "host=localhost;port=5432"
