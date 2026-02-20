"""Tests for LLM factory."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vizier.core.llm.factory import PROVIDER_KEY_MAP, create_llm_callable
from vizier.core.secrets.env_file_store import EnvFileSecretStore
from vizier.core.secrets.store import SecretNotFoundError


class TestCreateLLMCallable:
    def _make_store(self, tmp_path: Path, content: str) -> EnvFileSecretStore:
        env_file = tmp_path / ".env"
        env_file.write_text(content)
        return EnvFileSecretStore(env_file)

    def test_creates_callable_with_anthropic_key(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "ANTHROPIC_API_KEY=sk-test-123\n")
        llm = create_llm_callable(store, provider="anthropic")
        assert callable(llm)

    def test_closure_captures_api_key(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "ANTHROPIC_API_KEY=sk-captured\n")
        llm = create_llm_callable(store)

        mock_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))])
        with patch("litellm.completion", return_value=mock_response) as mock_completion:
            result = llm(model="claude-sonnet-4-6", messages=[{"role": "user", "content": "test"}])

        mock_completion.assert_called_once_with(
            api_key="sk-captured",
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result == mock_response

    def test_raises_on_missing_key(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "OTHER_KEY=val\n")
        with pytest.raises(SecretNotFoundError, match="ANTHROPIC_API_KEY not found"):
            create_llm_callable(store)

    def test_raises_on_empty_key(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "ANTHROPIC_API_KEY=\n")
        with pytest.raises(SecretNotFoundError, match="ANTHROPIC_API_KEY not found"):
            create_llm_callable(store)

    def test_raises_on_unknown_provider(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "KEY=val\n")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_callable(store, provider="nonexistent")

    def test_openai_provider(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path, "OPENAI_API_KEY=sk-openai\n")
        llm = create_llm_callable(store, provider="openai")
        assert callable(llm)

    def test_provider_key_map_has_expected_entries(self) -> None:
        assert "anthropic" in PROVIDER_KEY_MAP
        assert "openai" in PROVIDER_KEY_MAP
        assert "azure" in PROVIDER_KEY_MAP
