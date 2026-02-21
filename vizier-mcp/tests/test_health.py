"""Tests for the HTTP health and readiness endpoints."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from vizier_mcp.health import (
    DEFAULT_HEALTH_PORT,
    build_health_payload,
    build_readiness_payload,
    start_health_server,
)
from vizier_mcp.server import TOOL_COUNT

pytestmark = pytest.mark.anyio

VERSION = "0.7.0"


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


class TestBuildReadinessPayload:
    def test_all_checks_pass(self, tmp_path: object) -> None:
        import pathlib

        root = pathlib.Path(str(tmp_path))
        projects = root / "projects"
        projects.mkdir(parents=True)

        env = {"VIZIER_ROOT": str(root), "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=False):
            payload = build_readiness_payload(VERSION, 12, 12)

        assert payload["ready"] is True
        assert payload["version"] == VERSION
        assert payload["checks"]["tools"]["pass"] is True
        assert payload["checks"]["vizier_root"]["pass"] is True
        assert payload["checks"]["projects_dir"]["pass"] is True
        assert payload["checks"]["writable"]["pass"] is True
        assert payload["checks"]["anthropic_api_key"]["pass"] is True

    def test_wrong_tool_count_fails(self, tmp_path: object) -> None:
        import pathlib

        root = pathlib.Path(str(tmp_path))
        (root / "projects").mkdir(parents=True)

        env = {"VIZIER_ROOT": str(root), "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=False):
            payload = build_readiness_payload(VERSION, 5, 12)

        assert payload["ready"] is False
        assert payload["checks"]["tools"]["pass"] is False

    def test_missing_vizier_root_fails(self) -> None:
        env = {"VIZIER_ROOT": "/nonexistent/path", "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=False):
            payload = build_readiness_payload(VERSION, 12, 12)

        assert payload["ready"] is False
        assert payload["checks"]["vizier_root"]["pass"] is False
        assert payload["checks"]["projects_dir"]["pass"] is False

    def test_missing_api_key_fails(self, tmp_path: object) -> None:
        import pathlib

        root = pathlib.Path(str(tmp_path))
        (root / "projects").mkdir(parents=True)

        env = {"VIZIER_ROOT": str(root)}
        with patch.dict("os.environ", env, clear=True):
            payload = build_readiness_payload(VERSION, 12, 12)

        assert payload["ready"] is False
        assert payload["checks"]["anthropic_api_key"]["pass"] is False

    def test_missing_projects_dir_fails(self, tmp_path: object) -> None:
        import pathlib

        root = pathlib.Path(str(tmp_path))
        root.mkdir(exist_ok=True)

        env = {"VIZIER_ROOT": str(root), "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=False):
            payload = build_readiness_payload(VERSION, 12, 12)

        assert payload["ready"] is False
        assert payload["checks"]["projects_dir"]["pass"] is False


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

    async def test_readiness_endpoint_returns_json(self, tmp_path: object) -> None:
        import pathlib

        root = pathlib.Path(str(tmp_path))
        (root / "projects").mkdir(parents=True)

        env = {"VIZIER_ROOT": str(root), "ANTHROPIC_API_KEY": "test-key"}
        with patch.dict("os.environ", env, clear=False):
            server = await start_health_server(VERSION, TOOL_COUNT, host="127.0.0.1", port=0)
            port = server.sockets[0].getsockname()[1]

            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(b"GET /readiness HTTP/1.1\r\nHost: localhost\r\n\r\n")
                await writer.drain()

                response = await reader.read(4096)
                response_text = response.decode()

                assert "HTTP/1.1 200 OK" in response_text
                body = response_text.split("\r\n\r\n", 1)[1]
                data = json.loads(body)
                assert data["ready"] is True
                assert "checks" in data

                writer.close()
                await writer.wait_closed()
            finally:
                server.close()
                await server.wait_closed()

    async def test_readiness_returns_503_when_not_ready(self) -> None:
        env = {"VIZIER_ROOT": "/nonexistent/path"}
        with patch.dict("os.environ", env, clear=True):
            server = await start_health_server(VERSION, TOOL_COUNT, host="127.0.0.1", port=0)
            port = server.sockets[0].getsockname()[1]

            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                writer.write(b"GET /readiness HTTP/1.1\r\nHost: localhost\r\n\r\n")
                await writer.drain()

                response = await reader.read(4096)
                response_text = response.decode()

                assert "HTTP/1.1 503 Service Unavailable" in response_text
                body = response_text.split("\r\n\r\n", 1)[1]
                data = json.loads(body)
                assert data["ready"] is False

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
