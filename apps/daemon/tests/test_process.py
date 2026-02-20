"""Tests for daemon process module: Heartbeat, PingWatcher, AgentSpawner, VizierDaemon."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from vizier.daemon.process import AgentSpawner, Heartbeat, PingWatcher, VizierDaemon

# Re-use the mock_anthropic helpers from core tests
import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[3] / "libs" / "core" / "tests" / "runtime"))
from mock_anthropic import make_mock_client, make_text_response  # noqa: E402


class TestHeartbeat:
    def test_write_creates_json_file(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        heartbeat = Heartbeat(hb_path, interval_seconds=60)
        heartbeat._write()

        assert hb_path.exists()
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert "timestamp" in data
        assert "pid" in data
        assert "uptime_seconds" in data
        assert "cycle_count" in data
        assert "active_projects" in data

    def test_update_changes_data(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        heartbeat = Heartbeat(hb_path)
        heartbeat.update(cycle_count=5, active_projects=["alpha", "beta"])
        heartbeat._write()

        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert data["cycle_count"] == 5
        assert data["active_projects"] == ["alpha", "beta"]

    @pytest.mark.asyncio()
    async def test_start_stop_lifecycle(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        heartbeat = Heartbeat(hb_path, interval_seconds=0.05)

        await heartbeat.start()
        await asyncio.sleep(0.15)
        await heartbeat.stop()

        assert hb_path.exists()
        data = json.loads(hb_path.read_text(encoding="utf-8"))
        assert data["pid"] > 0

    def test_atomic_write_no_tmp_remains(self, tmp_path: Any) -> None:
        hb_path = tmp_path / "heartbeat.json"
        heartbeat = Heartbeat(hb_path)
        heartbeat._write()

        tmp_file = hb_path.with_suffix(".json.tmp")
        assert not tmp_file.exists()
        assert hb_path.exists()


class TestPingWatcher:
    @pytest.mark.asyncio()
    async def test_detects_new_ping_file(self, tmp_path: Any) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        wakeup = asyncio.Event()
        watcher = PingWatcher(str(specs_dir), wakeup)
        watcher.start()

        try:
            await asyncio.sleep(0.2)
            ping_dir = specs_dir / "001" / "pings"
            ping_dir.mkdir(parents=True)
            (ping_dir / "ping_001.json").write_text('{"urgency": "INFO"}', encoding="utf-8")
            await asyncio.sleep(0.5)
            assert wakeup.is_set()
        finally:
            watcher.stop()

    @pytest.mark.asyncio()
    async def test_ignores_non_ping_files(self, tmp_path: Any) -> None:
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        wakeup = asyncio.Event()
        watcher = PingWatcher(str(specs_dir), wakeup)
        watcher.start()

        try:
            await asyncio.sleep(0.2)
            (specs_dir / "readme.md").write_text("not a ping", encoding="utf-8")
            await asyncio.sleep(0.5)
            assert not wakeup.is_set()
        finally:
            watcher.stop()

    def test_start_stop_lifecycle(self, tmp_path: Any) -> None:
        specs_dir = tmp_path / "specs"
        wakeup = asyncio.Event()
        watcher = PingWatcher(str(specs_dir), wakeup)
        watcher.start()
        assert watcher._observer is not None
        watcher.stop()
        assert watcher._observer is None


class TestAgentSpawner:
    def test_make_spawn_callback_callable(self) -> None:
        client = make_mock_client(make_text_response("done"))
        spawner = AgentSpawner(client)
        callback = spawner.make_spawn_callback("/tmp/project")
        assert callable(callback)

    def test_spawn_sync_scout(self) -> None:
        client = make_mock_client(make_text_response("Research complete."))
        spawner = AgentSpawner(client)
        result = spawner._spawn_sync("scout", "001", {"task": "Research auth"}, "/tmp/project")
        assert result["role"] == "scout"
        assert result["spec_id"] == "001"
        assert "stop_reason" in result

    def test_spawn_sync_worker(self) -> None:
        client = make_mock_client(make_text_response("Implementation done."))
        spawner = AgentSpawner(client)
        result = spawner._spawn_sync(
            "worker", "002", {"task": "Implement auth", "goal": "Add login"}, "/tmp/project"
        )
        assert result["role"] == "worker"
        assert "stop_reason" in result

    def test_spawn_sync_unknown_role(self) -> None:
        client = make_mock_client()
        spawner = AgentSpawner(client)
        result = spawner._spawn_sync("unknown_agent", "001", {}, "/tmp/project")
        assert "error" in result
        assert "Unknown agent role" in result["error"]


class _FakeSecretStore:
    """Minimal mock secret store for testing."""

    def __init__(self, secrets: dict[str, str] | None = None) -> None:
        self._secrets = secrets or {}

    def get(self, key: str) -> str | None:
        return self._secrets.get(key)


class TestVizierDaemon:
    def _make_daemon(
        self, tmp_path: Any, secrets: dict[str, str] | None = None, projects: list[Any] | None = None
    ) -> VizierDaemon:
        from vizier.daemon.config import DaemonConfig, ProjectRegistry

        config = DaemonConfig(vizier_root=str(tmp_path), health_check_port=19876)
        registry = ProjectRegistry(projects=projects or [])
        if secrets is None:
            secrets = {"ANTHROPIC_API_KEY": "sk-test-fake-key"}
        store = _FakeSecretStore(secrets)
        return VizierDaemon(config, registry, store)

    def _setup_with_mock(self, daemon: VizierDaemon) -> Any:
        from unittest.mock import patch

        mock_client = make_mock_client(make_text_response("ok"))
        with patch.object(VizierDaemon, "_create_anthropic_client", return_value=mock_client):
            daemon.setup()
        return mock_client

    def test_setup_creates_client(self, tmp_path: Any) -> None:
        daemon = self._make_daemon(tmp_path)
        self._setup_with_mock(daemon)

        assert daemon._client is not None
        assert daemon._sentinel is not None
        assert daemon._ea_handler is not None
        assert daemon._spawner is not None

    def test_setup_no_api_key_raises(self, tmp_path: Any) -> None:
        daemon = self._make_daemon(tmp_path, secrets={})
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            daemon.setup()

    def test_get_status_keys(self, tmp_path: Any) -> None:
        daemon = self._make_daemon(tmp_path)
        status = daemon.get_status()
        assert "running" in status
        assert "projects" in status
        assert "project_names" in status
        assert "autonomy_stage" in status
        assert "cycles" in status

    @pytest.mark.asyncio()
    async def test_run_once_no_projects(self, tmp_path: Any) -> None:
        daemon = self._make_daemon(tmp_path)
        self._setup_with_mock(daemon)

        results = await daemon.run_once()
        assert results == {}

    @pytest.mark.asyncio()
    async def test_run_once_idle_project(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from vizier.daemon.config import ProjectEntry

        project_dir = tmp_path / "workspaces" / "alpha"
        project_dir.mkdir(parents=True)

        daemon = self._make_daemon(tmp_path, projects=[ProjectEntry(name="alpha")])
        self._setup_with_mock(daemon)

        results = await daemon.run_once()
        assert "alpha" in results
        assert results["alpha"]["status"] == "idle"

    @pytest.mark.asyncio()
    async def test_run_once_with_ready_specs(self, tmp_path: Any) -> None:
        from unittest.mock import patch

        from vizier.daemon.config import ProjectEntry

        project_dir = tmp_path / "workspaces" / "beta"
        specs_dir = project_dir / ".vizier" / "specs" / "001"
        specs_dir.mkdir(parents=True)
        (specs_dir / "state.json").write_text('{"status": "READY"}', encoding="utf-8")

        daemon = self._make_daemon(tmp_path, projects=[ProjectEntry(name="beta")])
        mock_client = make_mock_client(make_text_response("Pasha handled it."))
        with patch.object(VizierDaemon, "_create_anthropic_client", return_value=mock_client):
            daemon.setup()

        results = await daemon.run_once()
        assert "beta" in results
        assert results["beta"]["status"] == "active"

    def test_telegram_not_created_without_token(self, tmp_path: Any) -> None:
        daemon = self._make_daemon(tmp_path)
        self._setup_with_mock(daemon)
        assert daemon._telegram is None

    @pytest.mark.asyncio()
    async def test_shutdown_stops_subsystems(self, tmp_path: Any) -> None:
        from unittest.mock import AsyncMock

        daemon = self._make_daemon(tmp_path)
        self._setup_with_mock(daemon)

        daemon._health_server.stop = AsyncMock()
        daemon._heartbeat.stop = AsyncMock()  # type: ignore[union-attr]

        await daemon.shutdown()

        assert not daemon._running
        daemon._health_server.stop.assert_awaited_once()
        daemon._heartbeat.stop.assert_awaited_once()  # type: ignore[union-attr]
