"""Tests for MCP transport configuration in __main__.py."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vizier_mcp.__main__ import (
    DEFAULT_MCP_PORT,
    _mcp_port,
    _mcp_transport,
    _run_with_health,
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


class TestRunWithHealthCrashDetection:
    """Tests that _run_with_health exits when the MCP task crashes."""

    @pytest.mark.anyio
    async def test_mcp_task_crash_propagates_error(self) -> None:
        """If the MCP server task raises, _run_with_health re-raises instead of blocking."""
        mock_server = MagicMock()
        mock_server.run_async = AsyncMock(side_effect=OSError("Address already in use"))

        mock_health_srv = AsyncMock()
        mock_health_srv.close = MagicMock()
        mock_health_srv.wait_closed = AsyncMock()

        with (
            patch("vizier_mcp.__main__.create_server", return_value=mock_server),
            patch("vizier_mcp.__main__.start_health_server", new=AsyncMock(return_value=mock_health_srv)),
            pytest.raises(OSError, match="Address already in use"),
        ):
            await _run_with_health(health_port=18080, transport="stdio")

        mock_health_srv.close.assert_called_once()
        mock_health_srv.wait_closed.assert_awaited_once()

    @pytest.mark.anyio
    async def test_mcp_task_clean_exit_does_not_hang(self) -> None:
        """If the MCP server task exits cleanly, _run_with_health returns (not hangs)."""
        mock_server = MagicMock()
        mock_server.run_async = AsyncMock(return_value=None)

        mock_health_srv = AsyncMock()
        mock_health_srv.close = MagicMock()
        mock_health_srv.wait_closed = AsyncMock()

        with (
            patch("vizier_mcp.__main__.create_server", return_value=mock_server),
            patch("vizier_mcp.__main__.start_health_server", new=AsyncMock(return_value=mock_health_srv)),
        ):
            await asyncio.wait_for(_run_with_health(health_port=18080, transport="stdio"), timeout=5.0)

        mock_health_srv.close.assert_called_once()
