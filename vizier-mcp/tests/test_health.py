"""Tests for the HTTP health endpoint."""

from __future__ import annotations

import asyncio
import json

import pytest

from vizier_mcp.health import (
    DEFAULT_HEALTH_PORT,
    build_health_payload,
    start_health_server,
)
from vizier_mcp.server import TOOL_COUNT

pytestmark = pytest.mark.anyio

VERSION = "0.6.0"


class TestBuildHealthPayload:
    def test_returns_expected_fields(self) -> None:
        payload = build_health_payload(VERSION, TOOL_COUNT)
        assert payload == {
            "status": "ok",
            "version": VERSION,
            "tool_count": TOOL_COUNT,
        }

    def test_custom_values(self) -> None:
        payload = build_health_payload("1.2.3", 5)
        assert payload["version"] == "1.2.3"
        assert payload["tool_count"] == 5
        assert payload["status"] == "ok"


class TestHealthServer:
    async def test_health_endpoint_returns_200(self) -> None:
        server = await start_health_server(VERSION, TOOL_COUNT, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()

            response = await reader.read(4096)
            response_text = response.decode()

            assert "HTTP/1.1 200 OK" in response_text
            assert "application/json" in response_text

            body = response_text.split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert data["status"] == "ok"
            assert data["version"] == VERSION
            assert data["tool_count"] == TOOL_COUNT

            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    async def test_unknown_path_returns_404(self) -> None:
        server = await start_health_server(VERSION, TOOL_COUNT, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]

        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /unknown HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()

            response = await reader.read(4096)
            response_text = response.decode()

            assert "HTTP/1.1 404 Not Found" in response_text

            writer.close()
            await writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()

    async def test_uses_port_zero_for_ephemeral(self) -> None:
        server = await start_health_server(VERSION, TOOL_COUNT, host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        assert port > 0
        server.close()
        await server.wait_closed()

    async def test_default_port_constant(self) -> None:
        assert DEFAULT_HEALTH_PORT == 8080
