"""Simple HTTP health check endpoint for daemon monitoring."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vizier.daemon.process import VizierDaemon

logger = logging.getLogger(__name__)


class HealthCheckServer:
    """Minimal HTTP server returning daemon health status.

    :param daemon: The VizierDaemon instance to report on.
    :param port: TCP port to listen on.
    :param host: Host address to bind to.
    """

    def __init__(self, daemon: VizierDaemon, port: int = 8080, host: str = "0.0.0.0") -> None:
        self._daemon = daemon
        self._port = port
        self._host = host
        self._server: asyncio.Server | None = None

    async def start(self) -> None:
        """Start the health check HTTP server."""
        self._server = await asyncio.start_server(
            self._handle_request,
            self._host,
            self._port,
        )
        logger.info("Health check server listening on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the health check server."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Health check server stopped")

    async def _handle_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a single HTTP request."""
        try:
            data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            request_line = data.decode("utf-8", errors="replace").split("\r\n")[0]

            if "GET /health" in request_line or "GET / " in request_line:
                status = self._daemon.get_status()
                body = json.dumps(status, indent=2)
                response = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )
            else:
                body = '{"error": "Not Found"}'
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: application/json\r\n"
                    f"Content-Length: {len(body)}\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    f"{body}"
                )

            writer.write(response.encode("utf-8"))
            await writer.drain()
        except Exception:
            logger.exception("Error handling health check request")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
