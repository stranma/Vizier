"""Mock helpers simulating Anthropic API response structures for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock


@dataclass
class MockTextBlock:
    """Simulates anthropic.types.TextBlock."""

    text: str
    type: str = "text"


@dataclass
class MockToolUseBlock:
    """Simulates anthropic.types.ToolUseBlock."""

    id: str
    name: str
    input: dict[str, Any]
    type: str = "tool_use"


@dataclass
class MockUsage:
    """Simulates anthropic.types.Usage."""

    input_tokens: int = 100
    output_tokens: int = 50


@dataclass
class MockResponse:
    """Simulates anthropic.types.Message."""

    content: list[MockTextBlock | MockToolUseBlock] = field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: MockUsage = field(default_factory=MockUsage)


def make_text_response(text: str, *, input_tokens: int = 100, output_tokens: int = 50) -> MockResponse:
    """Create a response that contains only text (end_turn)."""
    return MockResponse(
        content=[MockTextBlock(text=text)],
        stop_reason="end_turn",
        usage=MockUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def make_tool_use_response(
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    tool_id: str = "toolu_01",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MockResponse:
    """Create a response that requests a tool call."""
    return MockResponse(
        content=[MockToolUseBlock(id=tool_id, name=tool_name, input=tool_input)],
        stop_reason="tool_use",
        usage=MockUsage(input_tokens=input_tokens, output_tokens=output_tokens),
    )


def make_mock_client(*responses: MockResponse) -> MagicMock:
    """Create a mock Anthropic client that returns responses in sequence.

    :param responses: Sequence of MockResponse objects to return from messages.create.
    :returns: MagicMock with .messages.create configured as side_effect.
    """
    client = MagicMock()
    client.messages.create.side_effect = list(responses)
    return client
