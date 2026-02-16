"""Tests for VCR record/replay infrastructure."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vizier.core.testing.vcr import VCRMode, VizierVCR, get_vcr_mode


class TestVCRMode:
    def test_default_mode_is_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("VIZIER_VCR_MODE", raising=False)
        assert get_vcr_mode() == VCRMode.OFF

    def test_record_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "record")
        assert get_vcr_mode() == VCRMode.RECORD

    def test_replay_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "replay")
        assert get_vcr_mode() == VCRMode.REPLAY

    def test_invalid_mode_defaults_to_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "invalid")
        assert get_vcr_mode() == VCRMode.OFF

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "RECORD")
        assert get_vcr_mode() == VCRMode.RECORD


class TestVizierVCR:
    def test_off_mode_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "off")
        vcr = VizierVCR(cassette_dir=tmp_path)
        with pytest.raises(RuntimeError, match="VCR is off"):
            vcr.completion(model="test-model", messages=[{"role": "user", "content": "hi"}])

    def test_record_saves_cassette(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "record")
        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(role="assistant", content="hello back"),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            model="test-model",
        )
        mock_llm = MagicMock(return_value=mock_response)

        vcr = VizierVCR(cassette_dir=tmp_path, real_llm=mock_llm)
        result = vcr.completion(model="test-model", messages=[{"role": "user", "content": "hi"}])

        mock_llm.assert_called_once()
        assert result is mock_response

        cassettes = list(tmp_path.glob("*.json"))
        assert len(cassettes) == 1

        data = json.loads(cassettes[0].read_text(encoding="utf-8"))
        assert data["request"]["model"] == "test-model"
        assert data["response"]["choices"][0]["message"]["content"] == "hello back"

    def test_replay_returns_recorded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "record")
        mock_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(role="assistant", content="recorded response"),
                    finish_reason="stop",
                )
            ],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
            model="test-model",
        )
        mock_llm = MagicMock(return_value=mock_response)

        vcr_record = VizierVCR(cassette_dir=tmp_path, real_llm=mock_llm)
        vcr_record.completion(model="test-model", messages=[{"role": "user", "content": "test"}])

        monkeypatch.setenv("VIZIER_VCR_MODE", "replay")
        vcr_replay = VizierVCR(cassette_dir=tmp_path)
        result = vcr_replay.completion(model="test-model", messages=[{"role": "user", "content": "test"}])

        assert isinstance(result, dict)
        assert result["choices"][0]["message"]["content"] == "recorded response"

    def test_replay_missing_cassette_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "replay")
        vcr = VizierVCR(cassette_dir=tmp_path)
        with pytest.raises(FileNotFoundError, match="No cassette found"):
            vcr.completion(model="test-model", messages=[{"role": "user", "content": "missing"}])

    def test_record_without_llm_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "record")
        vcr = VizierVCR(cassette_dir=tmp_path)
        with pytest.raises(RuntimeError, match="requires a real LLM"):
            vcr.completion(model="test-model", messages=[{"role": "user", "content": "hi"}])

    def test_deterministic_hashing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VIZIER_VCR_MODE", "record")
        mock_response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content="ok"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=2),
            model="m",
        )
        mock_llm = MagicMock(return_value=mock_response)

        vcr1 = VizierVCR(cassette_dir=tmp_path, real_llm=mock_llm)
        vcr1.completion(model="m", messages=[{"role": "user", "content": "same"}])

        vcr2 = VizierVCR(cassette_dir=tmp_path, real_llm=mock_llm)
        vcr2.completion(model="m", messages=[{"role": "user", "content": "same"}])

        cassettes = list(tmp_path.glob("*.json"))
        assert len(cassettes) == 1
