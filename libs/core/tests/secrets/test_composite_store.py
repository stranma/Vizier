"""Tests for CompositeSecretStore."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from vizier.core.secrets.composite_store import CompositeSecretStore
from vizier.core.secrets.env_file_store import EnvFileSecretStore


def _make_env_store(tmp_path: Path, name: str, content: str) -> EnvFileSecretStore:
    env_file = tmp_path / name
    env_file.write_text(content)
    return EnvFileSecretStore(env_file)


class TestCompositeSecretStore:
    def test_requires_at_least_one_backend(self) -> None:
        with pytest.raises(ValueError, match="at least one backend"):
            CompositeSecretStore([])

    def test_get_from_first_backend(self, tmp_path: Path) -> None:
        primary = _make_env_store(tmp_path, "primary.env", "KEY=primary_val\n")
        fallback = _make_env_store(tmp_path, "fallback.env", "KEY=fallback_val\n")

        store = CompositeSecretStore([primary, fallback])
        assert store.get("KEY") == "primary_val"

    def test_fallback_on_missing_key(self, tmp_path: Path) -> None:
        primary = _make_env_store(tmp_path, "primary.env", "OTHER=val\n")
        fallback = _make_env_store(tmp_path, "fallback.env", "FALLBACK_KEY=fallback_val\n")

        store = CompositeSecretStore([primary, fallback])
        assert store.get("FALLBACK_KEY") == "fallback_val"

    def test_get_returns_none_when_not_in_any(self, tmp_path: Path) -> None:
        backend = _make_env_store(tmp_path, "store.env", "KEY=val\n")

        store = CompositeSecretStore([backend])
        assert store.get("MISSING") is None

    def test_has_checks_all_backends(self, tmp_path: Path) -> None:
        primary = _make_env_store(tmp_path, "a.env", "A=1\n")
        secondary = _make_env_store(tmp_path, "b.env", "B=2\n")

        store = CompositeSecretStore([primary, secondary])
        assert store.has("A")
        assert store.has("B")
        assert not store.has("C")

    def test_is_non_empty_checks_all_backends(self, tmp_path: Path) -> None:
        primary = _make_env_store(tmp_path, "a.env", "FILLED=val\n")
        secondary = _make_env_store(tmp_path, "b.env", "EMPTY=\n")

        store = CompositeSecretStore([primary, secondary])
        assert store.is_non_empty("FILLED")
        assert not store.is_non_empty("EMPTY")

    def test_keys_deduplicated_and_sorted(self, tmp_path: Path) -> None:
        primary = _make_env_store(tmp_path, "a.env", "B=1\nA=2\n")
        secondary = _make_env_store(tmp_path, "b.env", "A=3\nC=4\n")

        store = CompositeSecretStore([primary, secondary])
        assert store.keys() == ["A", "B", "C"]

    def test_set_goes_to_first_writable(self, tmp_path: Path) -> None:
        """With only read-only backends, set raises NotImplementedError."""
        backend = _make_env_store(tmp_path, "store.env", "KEY=val\n")
        store = CompositeSecretStore([backend])

        with pytest.raises(NotImplementedError, match="No writable backend"):
            store.set("NEW", "val")

    def test_delete_goes_to_first_writable(self, tmp_path: Path) -> None:
        """With only read-only backends, delete raises NotImplementedError."""
        backend = _make_env_store(tmp_path, "store.env", "KEY=val\n")
        store = CompositeSecretStore([backend])

        with pytest.raises(NotImplementedError, match="No writable backend"):
            store.delete("KEY")

    def test_single_backend(self, tmp_path: Path) -> None:
        backend = _make_env_store(tmp_path, "store.env", "KEY=val\n")
        store = CompositeSecretStore([backend])
        assert store.get("KEY") == "val"
        assert store.keys() == ["KEY"]
