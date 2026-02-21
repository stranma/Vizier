"""Entry point for ``python -m vizier_mcp``.

Starts the MCP server with an optional HTTP health endpoint
for deployment monitoring (enabled when HEALTH_PORT is set or
when running inside Docker).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from vizier_mcp.health import DEFAULT_HEALTH_PORT, start_health_server
from vizier_mcp.server import TOOL_COUNT, create_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vizier_mcp")


def _health_port() -> int | None:
    """Return the health port if the health endpoint should be enabled."""
    raw = os.environ.get("HEALTH_PORT")
    if raw is not None:
        return int(raw)
    if os.path.exists("/.dockerenv"):
        return DEFAULT_HEALTH_PORT
    return None


async def _run_with_health(port: int) -> None:
    """Run MCP server alongside the health endpoint."""
    mcp = create_server()
    version: str = mcp.settings.version or "unknown"

    health_srv = await start_health_server(version, TOOL_COUNT, port=port)
    logger.info("Vizier MCP server starting (version=%s, tools=%d)", version, TOOL_COUNT)

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _signal_handler() -> None:
        if not stop.done():
            stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        await stop
    finally:
        health_srv.close()
        await health_srv.wait_closed()
        logger.info("Health server stopped")


def main() -> None:
    """Entry point: start MCP server, optionally with health endpoint."""
    port = _health_port()

    if port is not None:
        logger.info("Health endpoint enabled on port %d", port)
        asyncio.run(_run_with_health(port))
    else:
        server = create_server()
        logger.info("Starting MCP server (stdio transport, no health endpoint)")
        server.run()


if __name__ == "__main__":
    main()
