"""Vizier daemon application."""

__version__ = "0.8.0"

from vizier.daemon.config import DaemonConfig, ProjectEntry, ProjectRegistry
from vizier.daemon.health import HealthCheckServer
from vizier.daemon.process import AgentSpawner, Heartbeat, PingWatcher, VizierDaemon
from vizier.daemon.telegram import TelegramTransport

__all__ = [
    "AgentSpawner",
    "DaemonConfig",
    "Heartbeat",
    "HealthCheckServer",
    "PingWatcher",
    "ProjectEntry",
    "ProjectRegistry",
    "TelegramTransport",
    "VizierDaemon",
]
