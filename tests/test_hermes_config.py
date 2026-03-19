"""Tests for hermes/ -- validates Hermes Agent configuration for Vizier.

Ensures the Hermes config, SOUL.md, AGENTS.md, Dockerfile, and scripts
are present, structurally valid, and correctly wired for the Vizier MCP server.
"""

from pathlib import Path

import pytest
import yaml

HERMES_DIR = Path(__file__).parent.parent / "hermes"
CONFIG_PATH = HERMES_DIR / "config.yaml"
SOUL_PATH = HERMES_DIR / "SOUL.md"
AGENTS_PATH = HERMES_DIR / "AGENTS.md"
DOCKERFILE_PATH = HERMES_DIR / "Dockerfile"
ENTRYPOINT_PATH = HERMES_DIR / "scripts" / "entrypoint.sh"
HEALTHCHECK_PATH = HERMES_DIR / "scripts" / "healthcheck.sh"


class TestHermesFileExistence:
    """Verify all required Hermes configuration files exist."""

    @pytest.mark.parametrize(
        "path",
        [CONFIG_PATH, SOUL_PATH, AGENTS_PATH, DOCKERFILE_PATH, ENTRYPOINT_PATH, HEALTHCHECK_PATH],
        ids=["config.yaml", "SOUL.md", "AGENTS.md", "Dockerfile", "entrypoint.sh", "healthcheck.sh"],
    )
    def test_file_exists(self, path: Path) -> None:
        assert path.exists(), f"Missing: {path.relative_to(HERMES_DIR)}"


class TestHermesConfigStructure:
    """Validate config.yaml has required Hermes settings."""

    @pytest.fixture
    def config(self) -> dict:
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_model_provider_is_anthropic(self, config: dict) -> None:
        assert config["model"]["provider"] == "anthropic"

    def test_model_default_is_opus(self, config: dict) -> None:
        assert "opus" in config["model"]["default"], "Vizier should use an Opus-tier model"

    def test_fallback_model_configured(self, config: dict) -> None:
        fallback = config["fallback_model"]
        assert fallback["provider"] == "anthropic"
        assert "sonnet" in fallback["model"], "Fallback should be a Sonnet-tier model"

    def test_mcp_server_vizier_configured(self, config: dict) -> None:
        servers = config["mcp_servers"]
        assert "vizier" in servers, "Missing 'vizier' MCP server in config"
        vizier_mcp = servers["vizier"]
        assert "url" in vizier_mcp, "vizier MCP server needs a url"
        assert "vizier-mcp" in vizier_mcp["url"], "URL should reference the vizier-mcp service"

    def test_mcp_server_has_timeouts(self, config: dict) -> None:
        vizier_mcp = config["mcp_servers"]["vizier"]
        assert vizier_mcp.get("timeout", 0) > 0, "vizier MCP server should have a timeout"
        assert vizier_mcp.get("connect_timeout", 0) > 0, "vizier MCP server should have a connect_timeout"

    def test_terminal_backend_is_local(self, config: dict) -> None:
        assert config["terminal"]["backend"] == "local"

    def test_memory_enabled(self, config: dict) -> None:
        assert config["memory"]["memory_enabled"] is True

    def test_compression_enabled(self, config: dict) -> None:
        assert config["compression"]["enabled"] is True

    def test_no_secrets_in_config(self, config: dict) -> None:
        """Config file must not contain API keys or tokens."""
        content = CONFIG_PATH.read_text(encoding="utf-8")
        assert "sk-ant-" not in content, "API key found in config"
        assert "sk-or-" not in content, "API key found in config"
        assert "BOT_TOKEN" not in content, "Bot token reference found in config"


class TestSoulMd:
    """Validate SOUL.md content for Vizier identity."""

    @pytest.fixture
    def soul_content(self) -> str:
        return SOUL_PATH.read_text(encoding="utf-8")

    def test_identifies_as_vizier(self, soul_content: str) -> None:
        assert "Vizier" in soul_content
        assert "Grand Vizier" in soul_content

    def test_mentions_sultan(self, soul_content: str) -> None:
        assert "Sultan" in soul_content

    def test_mentions_mcp_tools(self, soul_content: str) -> None:
        assert "MCP" in soul_content

    def test_mentions_reactive_design(self, soul_content: str) -> None:
        assert "reactive" in soul_content.lower()

    def test_no_openclaw_references(self, soul_content: str) -> None:
        assert "OpenClaw" not in soul_content, "SOUL.md should not reference OpenClaw"
        assert "openclaw" not in soul_content.lower(), "SOUL.md should not reference OpenClaw"

    def test_under_character_limit(self, soul_content: str) -> None:
        assert len(soul_content) <= 20000, f"SOUL.md exceeds 20,000 char limit: {len(soul_content)}"


class TestAgentsMd:
    """Validate AGENTS.md project context."""

    @pytest.fixture
    def agents_content(self) -> str:
        return AGENTS_PATH.read_text(encoding="utf-8")

    def test_lists_mcp_tools(self, agents_content: str) -> None:
        expected_tools = [
            "realm_list_projects",
            "realm_create_project",
            "realm_get_project",
            "container_start",
            "container_stop",
            "container_status",
        ]
        for tool in expected_tools:
            assert tool in agents_content, f"AGENTS.md missing tool reference: {tool}"

    def test_no_openclaw_references(self, agents_content: str) -> None:
        assert "OpenClaw" not in agents_content, "AGENTS.md should not reference OpenClaw"

    def test_under_character_limit(self, agents_content: str) -> None:
        assert len(agents_content) <= 20000, f"AGENTS.md exceeds 20,000 char limit: {len(agents_content)}"


class TestDockerfile:
    """Validate Hermes Dockerfile structure."""

    @pytest.fixture
    def dockerfile(self) -> str:
        return DOCKERFILE_PATH.read_text(encoding="utf-8")

    def test_uses_python_311(self, dockerfile: str) -> None:
        assert "python:3.11" in dockerfile

    def test_installs_hermes(self, dockerfile: str) -> None:
        assert "hermes-agent" in dockerfile

    def test_copies_config(self, dockerfile: str) -> None:
        assert "config.yaml" in dockerfile
        assert "SOUL.md" in dockerfile
        assert "AGENTS.md" in dockerfile

    def test_non_root_user(self, dockerfile: str) -> None:
        assert "USER hermes" in dockerfile

    def test_has_healthcheck(self, dockerfile: str) -> None:
        assert "HEALTHCHECK" in dockerfile

    def test_has_entrypoint(self, dockerfile: str) -> None:
        assert "ENTRYPOINT" in dockerfile


class TestDockerCompose:
    """Validate docker-compose.yml has Hermes instead of OpenClaw."""

    @pytest.fixture
    def compose(self) -> dict:
        compose_path = Path(__file__).parent.parent / "docker-compose.yml"
        return yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    def test_has_vizier_mcp_service(self, compose: dict) -> None:
        assert "vizier-mcp" in compose["services"]

    def test_has_hermes_service(self, compose: dict) -> None:
        assert "hermes" in compose["services"]

    def test_no_openclaw_service(self, compose: dict) -> None:
        assert "openclaw" not in compose["services"], "OpenClaw should be removed from docker-compose"

    def test_hermes_depends_on_vizier_mcp(self, compose: dict) -> None:
        hermes = compose["services"]["hermes"]
        assert "vizier-mcp" in hermes.get("depends_on", {}), "hermes should depend on vizier-mcp"

    def test_hermes_builds_from_hermes_dir(self, compose: dict) -> None:
        hermes = compose["services"]["hermes"]
        assert hermes["build"] == "hermes/", "hermes should build from hermes/ directory"

    def test_no_openclaw_volumes(self, compose: dict) -> None:
        volumes = compose.get("volumes", {})
        assert "openclaw-data" not in volumes, "openclaw-data volume should be removed"


class TestEnvExample:
    """Validate .env.example has Hermes-appropriate variables."""

    @pytest.fixture
    def env_content(self) -> str:
        env_path = Path(__file__).parent.parent / ".env.example"
        return env_path.read_text(encoding="utf-8")

    def test_has_anthropic_key(self, env_content: str) -> None:
        assert "ANTHROPIC_API_KEY" in env_content

    def test_has_telegram_token(self, env_content: str) -> None:
        assert "TELEGRAM_BOT_TOKEN" in env_content

    def test_has_telegram_allowed_users(self, env_content: str) -> None:
        assert "TELEGRAM_ALLOWED_USERS" in env_content

    def test_no_openclaw_specific_vars(self, env_content: str) -> None:
        assert "TELEGRAM_SULTAN_CHAT_ID" not in env_content, (
            "TELEGRAM_SULTAN_CHAT_ID is OpenClaw-specific; use TELEGRAM_ALLOWED_USERS for Hermes"
        )
