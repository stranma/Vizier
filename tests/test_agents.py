"""Tests for .claude/agents/ -- validates all agent files have correct frontmatter and structure."""

import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).parent.parent / ".claude" / "agents"

EXISTING_AGENTS = [
    "acceptance-criteria-validator.md",
    "agent-auditor.md",
    "code-quality-validator.md",
    "code-reviewer.md",
    "docs-updater.md",
    "implementation-tracker.md",
    "pr-writer.md",
    "review-responder.md",
    "spec-readiness-reviewer.md",
    "test-coverage-validator.md",
]

NEW_AGENTS = [
    "security-auditor.md",
    "refactoring-specialist.md",
    "output-evaluator.md",
]

ALL_AGENTS = EXISTING_AGENTS + NEW_AGENTS

VALID_MODELS = {"haiku", "sonnet", "opus"}
VALID_PERMISSION_MODES = {"plan", "dontAsk", "acceptEdits"}
VALID_TOOLS = {"Read", "Glob", "Grep", "Bash", "Edit", "Write", "NotebookEdit", "WebSearch", "WebFetch"}


@pytest.fixture
def agent_frontmatter() -> dict[str, dict[str, str]]:
    """Parse frontmatter from all agent files."""
    results: dict[str, dict[str, str]] = {}
    for agent_name in ALL_AGENTS:
        agent_path = AGENTS_DIR / agent_name
        if not agent_path.exists():
            continue
        content = agent_path.read_text(encoding="utf-8")
        if not content.startswith("---"):
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        frontmatter: dict[str, str] = {}
        for line in parts[1].strip().splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()
        results[agent_name] = frontmatter
    return results


class TestAgentExistence:
    """Verify all expected agent files exist."""

    def test_agents_directory_exists(self) -> None:
        assert AGENTS_DIR.exists(), f"{AGENTS_DIR} does not exist"
        assert AGENTS_DIR.is_dir(), f"{AGENTS_DIR} is not a directory"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_file_exists(self, agent_name: str) -> None:
        agent_path = AGENTS_DIR / agent_name
        assert agent_path.exists(), f"Agent file missing: {agent_name}"

    def test_total_agent_count(self) -> None:
        actual_agents = {f.name for f in AGENTS_DIR.iterdir() if f.is_file() and f.suffix == ".md"}
        assert len(actual_agents) >= len(ALL_AGENTS), (
            f"Expected at least {len(ALL_AGENTS)} agents, found {len(actual_agents)}"
        )


class TestAgentFrontmatter:
    """Verify all agents have valid frontmatter fields."""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_frontmatter(self, agent_name: str) -> None:
        agent_path = AGENTS_DIR / agent_name
        content = agent_path.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{agent_name} missing YAML frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{agent_name} has unclosed frontmatter"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_name(self, agent_name: str, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get(agent_name, {})
        assert "name" in fm, f"{agent_name} missing 'name' in frontmatter"
        expected_name = agent_name.replace(".md", "")
        assert fm["name"] == expected_name, f"{agent_name} name mismatch: {fm['name']!r} != {expected_name!r}"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_description(self, agent_name: str, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get(agent_name, {})
        assert "description" in fm, f"{agent_name} missing 'description' in frontmatter"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_model(self, agent_name: str, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get(agent_name, {})
        assert "model" in fm, f"{agent_name} missing 'model' in frontmatter"
        assert fm["model"] in VALID_MODELS, f"{agent_name} has invalid model: {fm['model']!r}"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_tools(self, agent_name: str, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get(agent_name, {})
        assert "tools" in fm, f"{agent_name} missing 'tools' in frontmatter"
        tools = {t.strip() for t in fm["tools"].split(",")}
        invalid = tools - VALID_TOOLS
        assert not invalid, f"{agent_name} has invalid tools: {invalid}"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_permission_mode(self, agent_name: str, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get(agent_name, {})
        assert "permissionMode" in fm, f"{agent_name} missing 'permissionMode' in frontmatter"
        assert fm["permissionMode"] in VALID_PERMISSION_MODES, (
            f"{agent_name} has invalid permissionMode: {fm['permissionMode']!r}"
        )


class TestAgentBody:
    """Verify agents have meaningful body content after frontmatter."""

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_has_body(self, agent_name: str) -> None:
        agent_path = AGENTS_DIR / agent_name
        content = agent_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert len(body) > 100, f"{agent_name} body is too short ({len(body)} chars)"

    @pytest.mark.parametrize("agent_name", ALL_AGENTS)
    def test_agent_body_has_heading(self, agent_name: str) -> None:
        agent_path = AGENTS_DIR / agent_name
        content = agent_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else ""
        assert re.search(r"^#+\s", body, re.MULTILINE), f"{agent_name} body missing markdown heading"


class TestNewAgentSpecifics:
    """Verify new agents have correct read-only/permission configurations."""

    def test_security_auditor_is_read_only(self, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get("security-auditor.md", {})
        assert fm.get("permissionMode") == "plan", "security-auditor should be read-only (permissionMode: plan)"
        tools = {t.strip() for t in fm.get("tools", "").split(",")}
        assert "Bash" not in tools, "security-auditor should not have Bash access"
        assert "Edit" not in tools, "security-auditor should not have Edit access"
        assert "Write" not in tools, "security-auditor should not have Write access"

    def test_refactoring_specialist_is_read_only(self, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get("refactoring-specialist.md", {})
        assert fm.get("permissionMode") == "plan", "refactoring-specialist should be read-only (permissionMode: plan)"
        tools = {t.strip() for t in fm.get("tools", "").split(",")}
        assert "Bash" not in tools, "refactoring-specialist should not have Bash access"

    def test_output_evaluator_uses_dontask(self, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get("output-evaluator.md", {})
        assert fm.get("permissionMode") == "dontAsk", (
            "output-evaluator should use dontAsk for automated pipeline integration"
        )

    def test_output_evaluator_uses_haiku(self, agent_frontmatter: dict[str, dict[str, str]]) -> None:
        fm = agent_frontmatter.get("output-evaluator.md", {})
        assert fm.get("model") == "haiku", "output-evaluator should use haiku model for efficiency"
