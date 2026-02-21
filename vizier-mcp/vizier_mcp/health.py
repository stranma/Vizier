"""Lightweight async HTTP health endpoint for deployment monitoring.

Runs alongside the MCP server on a configurable port (default 8080).
``GET /health`` returns JSON with server version, tool count, and status.
"""

from __future__ import annotations

import json
import logging
from asyncio import AbstractEventLoop, start_server
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from asyncio.streams import StreamReader, StreamWriter

logger = logging.getLogger(__name__)

DEFAULT_HEALTH_PORT = 8080
DEFAULT_HEALTH_HOST = "0.0.0.0"


def build_health_payload(version: str, tool_count: int) -> dict[str, Any]:
    """Build the JSON payload for the health endpoint."""
    return {
        "status": "ok",
        "version": version,
        "tool_count": tool_count,
    }


async def _handle_request(
    reader: StreamReader,
    writer: StreamWriter,
    version: str,
    tool_count: int,
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
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{payload}"
            )
        else:
            body = "Not Found"
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/plain\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )

        writer.write(response.encode())
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
    loop: AbstractEventLoop | None = None,
) -> Any:
    """Start the async TCP health server.

    :param version: Server version string for the health payload.
    :param tool_count: Number of registered MCP tools.
    :param host: Bind address (default 0.0.0.0).
    :param port: Bind port (default 8080).
    :param loop: Optional event loop (for testing).
    :return: asyncio.Server instance (call .close() to stop).
    """

    async def handler(reader: StreamReader, writer: StreamWriter) -> None:
        await _handle_request(reader, writer, version, tool_count)

    server = await start_server(handler, host, port)
    logger.info("Health endpoint listening on %s:%d", host, port)
    return server
