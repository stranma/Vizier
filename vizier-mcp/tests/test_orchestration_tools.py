"""Tests for orchestration MCP tools (orch_write_ping, project_get_config)."""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING

import yaml

from vizier_mcp.models.orchestration import PingMessage, PingUrgency
from vizier_mcp.tools.config_tool import project_get_config
from vizier_mcp.tools.orchestration import orch_write_ping

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"
SPEC_ID = "001-auth"


def _create_spec_dir(project_dir: Path) -> Path:
    """Create a spec directory for testing."""
    spec_dir = project_dir / "specs" / SPEC_ID
    spec_dir.mkdir(parents=True, exist_ok=True)
    return spec_dir


def _write_config_yaml(project_dir: Path, data: dict) -> None:
    """Write config.yaml for a test project."""
    config_yaml = project_dir / "config.yaml"
    config_yaml.write_text(yaml.dump(data))


class TestOrchWritePing:
    """Tests for orch_write_ping (AC-O1, AC-O2, AC-O3)."""

    def test_question_ping(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "How to handle OAuth?")
        assert result["written"] is True
        assert "path" in result

    def test_blocker_ping(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "BLOCKER", "Cannot access database")
        assert result["written"] is True
        assert "BLOCKER" in result["path"]

    def test_impossible_ping(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "IMPOSSIBLE", "Spec contradicts itself")
        assert result["written"] is True
        assert "IMPOSSIBLE" in result["path"]

    def test_invalid_urgency(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "CRITICAL", "test")
        assert "error" in result
        assert result.get("written") is None

    def test_ping_file_written_to_disk(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "test message")
        assert result["written"] is True
        ping_path = pathlib.Path(result["path"])
        assert ping_path.exists()

    def test_ping_file_is_valid_json(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "BLOCKER", "need help")
        ping_path = pathlib.Path(result["path"])
        data = json.loads(ping_path.read_text())
        assert data["spec_id"] == SPEC_ID
        assert data["urgency"] == "BLOCKER"
        assert data["message"] == "need help"
        assert "created_at" in data

    def test_ping_file_loadable_as_model(self, config: ServerConfig, project_dir: Path) -> None:
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "IMPOSSIBLE", "contradictory criteria")
        ping_path = pathlib.Path(result["path"])
        data = json.loads(ping_path.read_text())
        ping = PingMessage(**data)
        assert ping.urgency == PingUrgency.IMPOSSIBLE
        assert ping.message == "contradictory criteria"

    def test_ping_path_matches_formula(self, config: ServerConfig, project_dir: Path) -> None:
        """AC-O1/AC-O2: returned path matches {specs}/{spec_id}/pings/{timestamp}-{urgency}.json."""
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "test")
        path = result["path"]
        assert f"/specs/{SPEC_ID}/pings/" in path
        assert path.endswith("-QUESTION.json")

    def test_nonexistent_project(self, config: ServerConfig) -> None:
        result = orch_write_ping(config, "nonexistent-project", SPEC_ID, "QUESTION", "test")
        assert "error" in result

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = orch_write_ping(config, PROJECT_ID, "999-missing", "QUESTION", "test")
        assert "error" in result

    def test_two_pings_no_collision(self, config: ServerConfig, project_dir: Path) -> None:
        """AC-O7: Two pings for same spec with different urgencies produce separate files."""
        _create_spec_dir(project_dir)
        r1 = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "first ping")
        r2 = orch_write_ping(config, PROJECT_ID, SPEC_ID, "BLOCKER", "second ping")
        assert r1["written"] is True
        assert r2["written"] is True
        assert r1["path"] != r2["path"]
        assert pathlib.Path(r1["path"]).exists()
        assert pathlib.Path(r2["path"]).exists()

    def test_pings_directory_created_automatically(self, config: ServerConfig, project_dir: Path) -> None:
        """Pings dir should be created if it doesn't exist."""
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "test")
        assert result["written"] is True


class TestProjectGetConfig:
    """Tests for project_get_config (AC-O4, AC-O5)."""

    def test_load_full_config(self, config: ServerConfig, project_dir: Path) -> None:
        _write_config_yaml(
            project_dir,
            {
                "type": "software",
                "language": "python",
                "framework": "fastapi",
                "test_command": "pytest",
                "lint_command": "ruff check .",
                "type_command": "pyright",
                "settings": {"coverage_threshold": 80},
            },
        )
        result = project_get_config(config, PROJECT_ID)
        assert result["type"] == "software"
        assert result["language"] == "python"
        assert result["settings"]["coverage_threshold"] == 80

    def test_load_partial_config(self, config: ServerConfig, project_dir: Path) -> None:
        _write_config_yaml(project_dir, {"type": "documents"})
        result = project_get_config(config, PROJECT_ID)
        assert result["type"] == "documents"
        assert result["settings"] == {}

    def test_missing_config_returns_default(self, config: ServerConfig, project_dir: Path) -> None:
        """AC-O4: Missing config.yaml returns {"type": null, "settings": {}}."""
        result = project_get_config(config, PROJECT_ID)
        assert result["type"] is None
        assert result["settings"] == {}

    def test_nonexistent_project(self, config: ServerConfig) -> None:
        """AC-O5: Non-existent project returns error."""
        result = project_get_config(config, "nonexistent-project")
        assert "error" in result

    def test_malformed_yaml(self, config: ServerConfig, project_dir: Path) -> None:
        """AC-O5: Malformed YAML returns error."""
        config_yaml = project_dir / "config.yaml"
        config_yaml.write_text(":\n  - [bad yaml\n  {{{}")
        result = project_get_config(config, PROJECT_ID)
        assert "error" in result

    def test_empty_config_yaml(self, config: ServerConfig, project_dir: Path) -> None:
        config_yaml = project_dir / "config.yaml"
        config_yaml.write_text("")
        result = project_get_config(config, PROJECT_ID)
        assert result["type"] is None
        assert result["settings"] == {}

    def test_extra_fields_preserved(self, config: ServerConfig, project_dir: Path) -> None:
        """Unknown fields in config.yaml should be preserved in settings or returned."""
        _write_config_yaml(
            project_dir,
            {
                "type": "software",
                "settings": {"custom_key": "custom_value"},
            },
        )
        result = project_get_config(config, PROJECT_ID)
        assert result["settings"]["custom_key"] == "custom_value"


class TestOrchIntegration:
    """Integration tests (AC-O7)."""

    def test_ping_write_and_read_roundtrip(self, config: ServerConfig, project_dir: Path) -> None:
        """Write a ping, read it back, verify all fields match."""
        _create_spec_dir(project_dir)
        result = orch_write_ping(config, PROJECT_ID, SPEC_ID, "IMPOSSIBLE", "API does not exist")
        assert result["written"] is True

        ping_path = pathlib.Path(result["path"])
        data = json.loads(ping_path.read_text())
        ping = PingMessage(**data)
        assert ping.spec_id == SPEC_ID
        assert ping.urgency == PingUrgency.IMPOSSIBLE
        assert ping.message == "API does not exist"
        assert ping.created_at is not None

    def test_multiple_pings_different_urgencies(self, config: ServerConfig, project_dir: Path) -> None:
        """AC-O7: Two pings with different urgencies coexist."""
        _create_spec_dir(project_dir)
        r1 = orch_write_ping(config, PROJECT_ID, SPEC_ID, "QUESTION", "first")
        r2 = orch_write_ping(config, PROJECT_ID, SPEC_ID, "BLOCKER", "second")
        r3 = orch_write_ping(config, PROJECT_ID, SPEC_ID, "IMPOSSIBLE", "third")

        pings_dir = project_dir / "specs" / SPEC_ID / "pings"
        assert len(list(pings_dir.glob("*.json"))) == 3

        for r in [r1, r2, r3]:
            assert r["written"] is True
            assert pathlib.Path(r["path"]).exists()
