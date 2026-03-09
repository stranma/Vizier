"""Entry point for ``python -m vizier_mcp``.

Starts the MCP server with an optional HTTP health endpoint
for deployment monitoring (enabled when HEALTH_PORT is set or
when running inside Docker).

Supports two MCP transports controlled by ``MCP_TRANSPORT`` env var:

- ``stdio`` (default): Standard MCP stdio transport
- ``streamable-http``: Streamable HTTP transport on ``MCP_PORT`` (default 8001)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from typing import Literal

from vizier_mcp.health import DEFAULT_HEALTH_PORT, start_health_server
from vizier_mcp.server import TOOL_COUNT, __version__, create_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("vizier_mcp")

DEFAULT_MCP_PORT = 8001
MCP_TRANSPORTS = ("stdio", "streamable-http")
McpTransport = Literal["stdio", "streamable-http"]


def _health_port() -> int | None:
    """Return the health port if the health endpoint should be enabled."""
    raw = os.environ.get("HEALTH_PORT")
    if raw is not None:
        try:
            return int(raw)
        except ValueError:
            logger.error("HEALTH_PORT='%s' is not a valid integer", raw)
            raise
    if os.path.exists("/.dockerenv"):
        return DEFAULT_HEALTH_PORT
    return None


def _mcp_transport() -> McpTransport:
    """Return the MCP transport from ``MCP_TRANSPORT`` env var (default: stdio)."""
    raw = os.environ.get("MCP_TRANSPORT", "stdio")
    if raw not in MCP_TRANSPORTS:
        msg = f"MCP_TRANSPORT='{raw}' is not valid. Use one of: {MCP_TRANSPORTS}"
        raise ValueError(msg)
    return raw  # type: ignore[return-value]


def _mcp_port() -> int:
    """Return the MCP HTTP port from ``MCP_PORT`` env var (default: 8001)."""
    raw = os.environ.get("MCP_PORT", str(DEFAULT_MCP_PORT))
    try:
        return int(raw)
    except ValueError:
        logger.error("MCP_PORT='%s' is not a valid integer", raw)
        raise


async def _run_with_health(health_port: int, transport: McpTransport) -> None:
    """Run MCP server alongside the HTTP health endpoint.

    :param health_port: Port for the health/readiness HTTP endpoint.
    :param transport: MCP transport to use (stdio or streamable-http).
    """
    mcp = create_server()

    health_srv = await start_health_server(__version__, TOOL_COUNT, port=health_port)
    logger.info(
        "Vizier MCP server starting (version=%s, tools=%d, transport=%s)",
        __version__,
        TOOL_COUNT,
        transport,
    )

    if transport == "streamable-http":
        mcp_port = _mcp_port()
        logger.info("MCP HTTP transport on port %d", mcp_port)
        mcp_task = asyncio.create_task(
            mcp.run_http_async(
                transport="streamable-http",
                host="0.0.0.0",
                port=mcp_port,
                show_banner=False,
            )
        )
    else:
        mcp_task = asyncio.create_task(mcp.run_async(show_banner=False))

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _signal_handler() -> None:
        if not stop.done():
            stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        done, _pending = await asyncio.wait(
            [asyncio.ensure_future(stop), mcp_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if mcp_task in done:
            if mcp_task.cancelled():
                logger.warning("MCP server task was cancelled")
            else:
                exc = mcp_task.exception()
                if exc is not None:
                    logger.error("MCP server task failed: %s", exc)
                    raise exc
                else:
                    logger.warning("MCP server task exited unexpectedly")
    finally:
        mcp_task.cancel()
        # CancelledError: normal shutdown via cancel() above.
        # Exception: mcp_task already failed; re-raised from try block,
        # suppress here so health server cleanup proceeds.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await mcp_task
        health_srv.close()
        await health_srv.wait_closed()
        logger.info("Health server stopped")


def main() -> None:
    """Entry point: start MCP server, optionally with health endpoint."""
    health_port = _health_port()
    transport = _mcp_transport()

    if health_port is not None:
        logger.info("Health endpoint enabled on port %d", health_port)
        asyncio.run(_run_with_health(health_port, transport))
    elif transport == "streamable-http":
        logger.info("Health endpoint enabled on port %d (required for HTTP transport)", DEFAULT_HEALTH_PORT)
        asyncio.run(_run_with_health(DEFAULT_HEALTH_PORT, transport))
    else:
        server = create_server()
        logger.info("Starting MCP server (stdio transport, no health endpoint)")
        server.run()


if __name__ == "__main__":
    main()
