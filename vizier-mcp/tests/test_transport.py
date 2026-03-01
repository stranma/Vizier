"""Tests for MCP transport configuration in __main__.py."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from vizier_mcp.__main__ import (
    DEFAULT_MCP_PORT,
    _mcp_port,
    _mcp_transport,
)


class TestMcpTransport:
    """Tests for _mcp_transport() env var parsing."""

    def test_default_is_stdio(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MCP_TRANSPORT", None)
            assert _mcp_transport() == "stdio"

    def test_stdio_explicit(self) -> None:
        with patch.dict(os.environ, {"MCP_TRANSPORT": "stdio"}):
            assert _mcp_transport() == "stdio"

    def test_streamable_http(self) -> None:
        with patch.dict(os.environ, {"MCP_TRANSPORT": "streamable-http"}):
            assert _mcp_transport() == "streamable-http"

    def test_invalid_transport_raises(self) -> None:
        with patch.dict(os.environ, {"MCP_TRANSPORT": "websocket"}), pytest.raises(ValueError, match="not valid"):
            _mcp_transport()


class TestMcpPort:
    """Tests for _mcp_port() env var parsing."""

    def test_default_port(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MCP_PORT", None)
            assert _mcp_port() == DEFAULT_MCP_PORT

    def test_custom_port(self) -> None:
        with patch.dict(os.environ, {"MCP_PORT": "9000"}):
            assert _mcp_port() == 9000

    def test_invalid_port_raises(self) -> None:
        with patch.dict(os.environ, {"MCP_PORT": "not-a-number"}), pytest.raises(ValueError):
            _mcp_port()
