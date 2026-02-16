"""VCR record/replay for litellm calls (D41).

Controlled by VIZIER_VCR_MODE environment variable:
- record: Call real LLM, save request/response to cassette file
- replay: Load cassette, assert request matches, return recorded response
- off (default): Standard mock behavior (existing tests unchanged)
"""

from __future__ import annotations

import hashlib
import json
import os
from enum import StrEnum
from pathlib import Path
from typing import Any


class VCRMode(StrEnum):
    """VCR operating modes."""

    OFF = "off"
    RECORD = "record"
    REPLAY = "replay"


def get_vcr_mode() -> VCRMode:
    """Read VCR mode from environment.

    :returns: Current VCR mode.
    """
    raw = os.environ.get("VIZIER_VCR_MODE", "off").lower()
    try:
        return VCRMode(raw)
    except ValueError:
        return VCRMode.OFF


def _request_hash(model: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"model": model, "messages": messages}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class VizierVCR:
    """Record/replay wrapper for litellm.completion calls.

    :param cassette_dir: Directory for cassette JSON files.
    :param real_llm: The real litellm.completion function (for record mode).
    """

    def __init__(
        self,
        cassette_dir: str | Path,
        real_llm: Any = None,
    ) -> None:
        self._dir = Path(cassette_dir)
        self._real_llm = real_llm
        self._mode = get_vcr_mode()

    @property
    def mode(self) -> VCRMode:
        return self._mode

    def completion(self, *, model: str, messages: list[dict[str, str]], **kwargs: Any) -> Any:
        """Call LLM with VCR behavior based on mode.

        :param model: Model identifier.
        :param messages: Chat messages.
        :returns: LLM response (real or replayed).
        :raises FileNotFoundError: In replay mode when no cassette exists.
        :raises RuntimeError: In record mode when no real LLM is configured.
        """
        if self._mode == VCRMode.OFF:
            raise RuntimeError("VCR is off; use a mock or set VIZIER_VCR_MODE=record|replay")

        req_hash = _request_hash(model, messages)
        cassette_path = self._dir / f"{req_hash}.json"

        if self._mode == VCRMode.REPLAY:
            return self._replay(cassette_path, model, messages)

        return self._record(cassette_path, model, messages, **kwargs)

    def _record(
        self,
        cassette_path: Path,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        if self._real_llm is None:
            raise RuntimeError("VCR record mode requires a real LLM callable")

        response = self._real_llm(model=model, messages=messages, **kwargs)

        cassette_data = {
            "request": {"model": model, "messages": messages},
            "response": _serialize_response(response),
        }
        self._dir.mkdir(parents=True, exist_ok=True)
        cassette_path.write_text(json.dumps(cassette_data, indent=2, default=str), encoding="utf-8")

        return response

    def _replay(
        self,
        cassette_path: Path,
        model: str,
        messages: list[dict[str, str]],
    ) -> Any:
        if not cassette_path.exists():
            raise FileNotFoundError(f"No cassette found for request hash: {cassette_path.stem}")

        data = json.loads(cassette_path.read_text(encoding="utf-8"))
        return _deserialize_response(data["response"])


def _serialize_response(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response

    result: dict[str, Any] = {}
    if hasattr(response, "choices"):
        result["choices"] = []
        for choice in response.choices:
            choice_data: dict[str, Any] = {}
            if hasattr(choice, "message"):
                choice_data["message"] = {
                    "role": getattr(choice.message, "role", "assistant"),
                    "content": getattr(choice.message, "content", ""),
                }
            if hasattr(choice, "finish_reason"):
                choice_data["finish_reason"] = choice.finish_reason
            result["choices"].append(choice_data)

    if hasattr(response, "usage"):
        usage = response.usage
        result["usage"] = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
        }

    if hasattr(response, "model"):
        result["model"] = response.model

    return result


def _deserialize_response(data: dict[str, Any]) -> dict[str, Any]:
    return data
