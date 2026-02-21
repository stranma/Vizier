"""Lightweight async HTTP health and readiness endpoints for deployment monitoring.

Runs alongside the MCP server on a configurable port (default 8080).

- ``GET /health`` -- liveness probe: returns JSON with version, tool count, status.
- ``GET /readiness`` -- readiness probe: verifies tool registration, data directory
  access, and Anthropic API key presence.
"""

from __future__ import annotations

import json
import logging
import os
from asyncio import start_server
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from asyncio.streams import StreamReader, StreamWriter

logger = logging.getLogger(__name__)

DEFAULT_HEALTH_PORT = 8080
DEFAULT_HEALTH_HOST = "0.0.0.0"


def build_health_payload(version: str, tool_count: int) -> dict[str, Any]:
    """Build the JSON payload for the /health liveness endpoint."""
    return {
        "status": "ok",
        "version": version,
        "tool_count": tool_count,
    }


def build_readiness_payload(version: str, tool_count: int, expected_tools: int) -> dict[str, Any]:
    """Build the JSON payload for the /readiness endpoint.

    Checks:
    - Tool count matches expected (12 tools)
    - VIZIER_ROOT directory exists and is writable
    - projects/ subdirectory exists
    - ANTHROPIC_API_KEY is set (required for Sentinel Haiku evaluator)
    """
    checks: dict[str, dict[str, Any]] = {}

    checks["tools"] = {
        "pass": tool_count == expected_tools,
        "detail": f"{tool_count}/{expected_tools} tools registered",
    }

    vizier_root = Path(os.environ.get("VIZIER_ROOT", "/data/vizier"))
    root_exists = vizier_root.is_dir()
    checks["vizier_root"] = {
        "pass": root_exists,
        "detail": str(vizier_root),
    }

    if root_exists:
        projects_dir = vizier_root / "projects"
        projects_exists = projects_dir.is_dir()
        checks["projects_dir"] = {
            "pass": projects_exists,
            "detail": str(projects_dir),
        }
        try:
            writable = os.access(vizier_root, os.W_OK)
        except OSError:
            writable = False
        checks["writable"] = {
            "pass": writable,
            "detail": "data directory is writable" if writable else "data directory is NOT writable",
        }
    else:
        checks["projects_dir"] = {"pass": False, "detail": "vizier_root missing"}
        checks["writable"] = {"pass": False, "detail": "vizier_root missing"}

    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    checks["anthropic_api_key"] = {
        "pass": has_api_key,
        "detail": "set" if has_api_key else "NOT set",
    }

    all_pass = all(c["pass"] for c in checks.values())

    return {
        "ready": all_pass,
        "version": version,
        "checks": checks,
    }


def _json_response(status_code: int, status_text: str, payload: str) -> bytes:
    """Build an HTTP response with JSON body."""
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(payload.encode())}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{payload}"
    )
    return response.encode()


def _text_response(status_code: int, status_text: str, body: str) -> bytes:
    """Build an HTTP response with plain text body."""
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(body.encode())}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{body}"
    )
    return response.encode()


async def _handle_request(
    reader: StreamReader,
    writer: StreamWriter,
    version: str,
    tool_count: int,
    expected_tools: int,
) -> None:
    """Handle a single HTTP request on the health server."""
    try:
        request_line = await reader.readline()
        request_text = request_line.decode("utf-8", errors="replace").strip()

        while True:
            header = await reader.readline()
            if header in (b"\r\n", b"\n", b""):
                break

        if request_text.startswith("GET /health"):
            payload = json.dumps(build_health_payload(version, tool_count))
            writer.write(_json_response(200, "OK", payload))
        elif request_text.startswith("GET /readiness"):
            readiness = build_readiness_payload(version, tool_count, expected_tools)
            payload = json.dumps(readiness)
            code = 200 if readiness["ready"] else 503
            text = "OK" if readiness["ready"] else "Service Unavailable"
            writer.write(_json_response(code, text, payload))
        else:
            writer.write(_text_response(404, "Not Found", "Not Found"))

        await writer.drain()
    except Exception:
        logger.exception("Health endpoint request error")
    finally:
        writer.close()
        await writer.wait_closed()


async def start_health_server(
    version: str,
    tool_count: int,
    host: str = DEFAULT_HEALTH_HOST,
    port: int = DEFAULT_HEALTH_PORT,
    expected_tools: int = 12,
) -> Any:
    """Start the async TCP health server with /health and /readiness endpoints.

    :param version: Server version string for the health payload.
    :param tool_count: Number of registered MCP tools.
    :param host: Bind address (default 0.0.0.0).
    :param port: Bind port (default 8080).
    :param expected_tools: Expected tool count for readiness check (default 11).
    :return: asyncio.Server instance (call .close() to stop).
    """

    async def handler(reader: StreamReader, writer: StreamWriter) -> None:
        await _handle_request(reader, writer, version, tool_count, expected_tools)

    server = await start_server(handler, host, port)
    logger.info("Health endpoint listening on %s:%d", host, port)
    return server
