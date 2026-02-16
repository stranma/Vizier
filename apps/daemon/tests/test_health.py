"""Tests for health check HTTP server."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from vizier.daemon.health import HealthCheckServer


@pytest.fixture()
def mock_daemon() -> MagicMock:
    daemon = MagicMock()
    daemon.get_status.return_value = {
        "running": True,
        "projects": 2,
        "project_names": ["alpha", "beta"],
        "autonomy_stage": 1,
        "heartbeat": None,
    }
    return daemon


class TestHealthCheckServer:
    @pytest.mark.asyncio()
    async def test_health_endpoint(self, mock_daemon: MagicMock) -> None:
        server = HealthCheckServer(mock_daemon, port=0, host="127.0.0.1")
        await server.start()
        tcp_server = server._server
        assert tcp_server is not None

        addr = tcp_server.sockets[0].getsockname()
        reader, writer = await asyncio.open_connection("127.0.0.1", addr[1])

        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()

        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        response_str = response.decode("utf-8")
        assert "200 OK" in response_str
        assert "application/json" in response_str

        body_start = response_str.index("\r\n\r\n") + 4
        body = json.loads(response_str[body_start:])
        assert body["running"] is True
        assert body["projects"] == 2

        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio()
    async def test_root_endpoint(self, mock_daemon: MagicMock) -> None:
        server = HealthCheckServer(mock_daemon, port=0, host="127.0.0.1")
        await server.start()
        tcp_server = server._server
        assert tcp_server is not None

        addr = tcp_server.sockets[0].getsockname()
        reader, writer = await asyncio.open_connection("127.0.0.1", addr[1])

        writer.write(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()

        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert b"200 OK" in response

        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio()
    async def test_404_endpoint(self, mock_daemon: MagicMock) -> None:
        server = HealthCheckServer(mock_daemon, port=0, host="127.0.0.1")
        await server.start()
        tcp_server = server._server
        assert tcp_server is not None

        addr = tcp_server.sockets[0].getsockname()
        reader, writer = await asyncio.open_connection("127.0.0.1", addr[1])

        writer.write(b"GET /unknown HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()

        response = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert b"404 Not Found" in response

        writer.close()
        await writer.wait_closed()
        await server.stop()

    @pytest.mark.asyncio()
    async def test_stop_without_start(self, mock_daemon: MagicMock) -> None:
        server = HealthCheckServer(mock_daemon, port=0)
        await server.stop()
