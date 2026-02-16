"""Tests for VizierDaemon process and heartbeat."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vizier.daemon.config import DaemonConfig, ProjectEntry, ProjectRegistry, TelegramConfig
from vizier.daemon.process import Heartbeat, VizierDaemon, install_signal_handlers


class TestHeartbeat:
    def test_write_and_read(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        hb = Heartbeat(hb_path)
        hb.write(projects_active=3, agents_running=7)

        data = hb.read()
        assert data is not None
        assert data["projects_active"] == 3
        assert data["agents_running"] == 7
        assert "timestamp" in data
        assert "pid" in data

    def test_read_nonexistent(self, tmp_path: Any) -> None:
        hb = Heartbeat(tmp_path / "missing.json")
        assert hb.read() is None

    def test_read_corrupt_file(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        hb_path.write_text("not json", encoding="utf-8")
        hb = Heartbeat(hb_path)
        assert hb.read() is None

    def test_atomic_write(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        hb = Heartbeat(hb_path)
        hb.write(projects_active=1, agents_running=0)
        tmp_file = hb_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()
        assert hb_path.exists()

    def test_overwrite_existing(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        hb = Heartbeat(hb_path)
        hb.write(projects_active=1, agents_running=0)
        hb.write(projects_active=5, agents_running=3)
        data = hb.read()
        assert data is not None
        assert data["projects_active"] == 5
        assert data["agents_running"] == 3


class TestVizierDaemon:
    @pytest.fixture()
    def vizier_dir(self, tmp_path: Any) -> Path:
        root = tmp_path / "vizier"
        root.mkdir()
        (root / "workspaces").mkdir()
        (root / "reports").mkdir()
        (root / "ea").mkdir()
        return root

    @pytest.fixture()
    def config(self, vizier_dir: Path) -> DaemonConfig:
        return DaemonConfig(vizier_root=str(vizier_dir))

    @pytest.fixture()
    def registry(self, vizier_dir: Path) -> ProjectRegistry:
        ws = vizier_dir / "workspaces" / "alpha"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / ".vizier" / "specs").mkdir(parents=True)
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha", local_path=str(ws)))
        return reg

    def test_setup_creates_ea_and_pashas(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.setup()
        assert daemon.ea is not None
        assert "alpha" in daemon.pashas
        assert len(daemon.pashas) == 1

    def test_setup_empty_registry(self, config: DaemonConfig) -> None:
        daemon = VizierDaemon(config, ProjectRegistry())
        daemon.setup()
        assert daemon.ea is not None
        assert len(daemon.pashas) == 0

    def test_get_status_before_run(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.setup()
        status = daemon.get_status()
        assert status["running"] is False
        assert status["projects"] == 1
        assert "alpha" in status["project_names"]
        assert status["autonomy_stage"] == 1

    def test_is_running_initially_false(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        assert daemon.is_running is False

    def test_shutdown_sets_event(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.shutdown()
        assert daemon._shutdown_event.is_set()

    @pytest.mark.asyncio()
    async def test_run_once(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.setup()

        mock_report = MagicMock()
        mock_report.cycle = 1
        for pasha in daemon._pashas.values():
            pasha.run_once = AsyncMock(return_value=mock_report)

        with patch.object(daemon, "setup"):
            results = await daemon.run_once()
        assert "alpha" in results
        assert results["alpha"]["status"] == "ok"

    @pytest.mark.asyncio()
    async def test_run_once_handles_error(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.setup()
        for pasha in daemon._pashas.values():
            pasha.run_once = AsyncMock(side_effect=RuntimeError("test error"))

        with patch.object(daemon, "setup"):
            results = await daemon.run_once()
        assert results["alpha"]["status"] == "error"
        assert "test error" in results["alpha"]["error"]

    @pytest.mark.asyncio()
    async def test_run_and_shutdown(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        asyncio.get_event_loop().call_later(0.05, daemon.shutdown)
        run_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.2)
        assert not daemon.is_running
        await run_task

    def test_resolve_project_path_with_local_path(self, config: DaemonConfig) -> None:
        entry = ProjectEntry(name="alpha", local_path="/custom/alpha")
        daemon = VizierDaemon(config, ProjectRegistry())
        path = daemon._resolve_project_path(entry)
        assert path == Path("/custom/alpha")

    def test_resolve_project_path_default(self, config: DaemonConfig, vizier_dir: Path) -> None:
        entry = ProjectEntry(name="alpha")
        daemon = VizierDaemon(config, ProjectRegistry())
        path = daemon._resolve_project_path(entry)
        expected = vizier_dir / "workspaces" / "alpha"
        assert path == expected

    def test_multiple_projects(self, config: DaemonConfig, vizier_dir: Path) -> None:
        reg = ProjectRegistry()
        for name in ["alpha", "beta", "gamma"]:
            ws = vizier_dir / "workspaces" / name
            ws.mkdir(parents=True, exist_ok=True)
            (ws / ".vizier" / "specs").mkdir(parents=True)
            reg.add(ProjectEntry(name=name, local_path=str(ws)))

        daemon = VizierDaemon(config, reg)
        daemon.setup()
        assert len(daemon.pashas) == 3
        assert set(daemon.pashas.keys()) == {"alpha", "beta", "gamma"}

    def test_inactive_projects_excluded(self, config: DaemonConfig, vizier_dir: Path) -> None:
        reg = ProjectRegistry()
        ws_active = vizier_dir / "workspaces" / "active"
        ws_active.mkdir(parents=True, exist_ok=True)
        (ws_active / ".vizier" / "specs").mkdir(parents=True)
        reg.add(ProjectEntry(name="active", local_path=str(ws_active)))
        reg.add(ProjectEntry(name="inactive", active=False))

        daemon = VizierDaemon(config, reg)
        daemon.setup()
        assert "active" in daemon.pashas
        assert "inactive" not in daemon.pashas

    def test_heartbeat_written_after_run_once(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        daemon.setup()
        for pasha in daemon._pashas.values():
            pasha.run_once = AsyncMock(return_value=MagicMock(cycle=1))

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(daemon.run_once())
        finally:
            loop.close()

        hb_path = Path(config.vizier_root) / config.heartbeat_path
        assert hb_path.exists()


class TestHealthServerIntegration:
    @pytest.fixture()
    def vizier_dir(self, tmp_path: Any) -> Path:
        root = tmp_path / "vizier"
        root.mkdir()
        (root / "workspaces").mkdir()
        (root / "reports").mkdir()
        (root / "ea").mkdir()
        return root

    @pytest.fixture()
    def config(self, vizier_dir: Path) -> DaemonConfig:
        return DaemonConfig(vizier_root=str(vizier_dir))

    @pytest.fixture()
    def registry(self, vizier_dir: Path) -> ProjectRegistry:
        ws = vizier_dir / "workspaces" / "alpha"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / ".vizier" / "specs").mkdir(parents=True)
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha", local_path=str(ws)))
        return reg

    @pytest.mark.asyncio()
    async def test_run_starts_health_server(self, config: DaemonConfig, registry: ProjectRegistry) -> None:
        daemon = VizierDaemon(config, registry)
        mock_health = MagicMock()
        mock_health.start = AsyncMock()
        mock_health.stop = AsyncMock()

        with patch("vizier.daemon.process.HealthCheckServer", return_value=mock_health) as mock_cls:
            asyncio.get_event_loop().call_later(0.05, daemon.shutdown)
            await daemon.run()

            mock_cls.assert_called_once_with(daemon, port=config.health_check_port)
            mock_health.start.assert_awaited_once()
            mock_health.stop.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_health_server_uses_config_port(self, vizier_dir: Path, registry: ProjectRegistry) -> None:
        config = DaemonConfig(vizier_root=str(vizier_dir), health_check_port=9090)
        daemon = VizierDaemon(config, registry)
        mock_health = MagicMock()
        mock_health.start = AsyncMock()
        mock_health.stop = AsyncMock()

        with patch("vizier.daemon.process.HealthCheckServer", return_value=mock_health) as mock_cls:
            asyncio.get_event_loop().call_later(0.05, daemon.shutdown)
            await daemon.run()

            mock_cls.assert_called_once_with(daemon, port=9090)


class TestTelegramIntegration:
    @pytest.fixture()
    def vizier_dir(self, tmp_path: Any) -> Path:
        root = tmp_path / "vizier"
        root.mkdir()
        (root / "workspaces").mkdir()
        (root / "reports").mkdir()
        (root / "ea").mkdir()
        return root

    @pytest.fixture()
    def registry(self, vizier_dir: Path) -> ProjectRegistry:
        ws = vizier_dir / "workspaces" / "alpha"
        ws.mkdir(parents=True, exist_ok=True)
        (ws / ".vizier" / "specs").mkdir(parents=True)
        reg = ProjectRegistry()
        reg.add(ProjectEntry(name="alpha", local_path=str(ws)))
        return reg

    def test_resolve_telegram_config_from_config(self, vizier_dir: Path) -> None:
        config = DaemonConfig(
            vizier_root=str(vizier_dir),
            telegram=TelegramConfig(token="bot-token-123", allowed_user_ids=[111, 222]),
        )
        daemon = VizierDaemon(config, ProjectRegistry())
        result = daemon._resolve_telegram_config()
        assert result is not None
        token, ids = result
        assert token == "bot-token-123"
        assert ids == [111, 222]

    def test_resolve_telegram_config_from_store(self, vizier_dir: Path) -> None:
        config = DaemonConfig(vizier_root=str(vizier_dir))
        store = MagicMock()
        store.get = MagicMock(
            side_effect=lambda key: {
                "TELEGRAM_BOT_TOKEN": "store-token",
                "TELEGRAM_SULTAN_CHAT_ID": "100,200",
            }.get(key)
        )
        daemon = VizierDaemon(config, ProjectRegistry(), secret_store=store)
        result = daemon._resolve_telegram_config()
        assert result is not None
        token, ids = result
        assert token == "store-token"
        assert ids == [100, 200]

    def test_resolve_telegram_config_empty(self, vizier_dir: Path) -> None:
        config = DaemonConfig(vizier_root=str(vizier_dir))
        daemon = VizierDaemon(config, ProjectRegistry())
        result = daemon._resolve_telegram_config()
        assert result is None

    @pytest.mark.asyncio()
    async def test_run_starts_telegram_with_token(self, vizier_dir: Path, registry: ProjectRegistry) -> None:
        config = DaemonConfig(
            vizier_root=str(vizier_dir),
            telegram=TelegramConfig(token="bot-token"),
        )
        daemon = VizierDaemon(config, registry)

        mock_health = MagicMock()
        mock_health.start = AsyncMock()
        mock_health.stop = AsyncMock()

        mock_telegram = MagicMock()
        mock_telegram.setup = MagicMock()
        mock_telegram.start = AsyncMock()
        mock_telegram.stop = AsyncMock()

        with (
            patch("vizier.daemon.process.HealthCheckServer", return_value=mock_health),
            patch("vizier.daemon.process.TelegramTransport", return_value=mock_telegram) as mock_tg_cls,
        ):
            asyncio.get_event_loop().call_later(0.05, daemon.shutdown)
            await daemon.run()

            mock_tg_cls.assert_called_once()
            mock_telegram.setup.assert_called_once()
            mock_telegram.stop.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_run_skips_telegram_without_token(self, vizier_dir: Path, registry: ProjectRegistry) -> None:
        config = DaemonConfig(vizier_root=str(vizier_dir))
        daemon = VizierDaemon(config, registry)

        mock_health = MagicMock()
        mock_health.start = AsyncMock()
        mock_health.stop = AsyncMock()

        with (
            patch("vizier.daemon.process.HealthCheckServer", return_value=mock_health),
            patch("vizier.daemon.process.TelegramTransport") as mock_tg_cls,
        ):
            asyncio.get_event_loop().call_later(0.05, daemon.shutdown)
            await daemon.run()

            mock_tg_cls.assert_not_called()


class TestInstallSignalHandlers:
    def test_installs_handlers(self, tmp_path: Any) -> None:
        import contextlib

        config = DaemonConfig(vizier_root=str(tmp_path))
        daemon = VizierDaemon(config, ProjectRegistry())
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            with contextlib.suppress(NotImplementedError):
                install_signal_handlers(daemon)
        finally:
            loop.close()
