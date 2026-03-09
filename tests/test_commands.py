"""Tests for .claude/commands/ -- validates command files exist and have correct structure."""

from pathlib import Path

import pytest

COMMANDS_DIR = Path(__file__).parent.parent / ".claude" / "commands"

ALL_COMMANDS = [
    "catchup.md",
    "security-audit.md",
]


class TestCommandExistence:
    """Verify all expected command files exist."""

    def test_commands_directory_exists(self) -> None:
        assert COMMANDS_DIR.exists(), f"{COMMANDS_DIR} does not exist"
        assert COMMANDS_DIR.is_dir(), f"{COMMANDS_DIR} is not a directory"

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_file_exists(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        assert command_path.exists(), f"Command file missing: {command_name}"


class TestCommandStructure:
    """Verify command files have correct frontmatter and content."""

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_has_frontmatter(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        content = command_path.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{command_name} missing YAML frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{command_name} has unclosed frontmatter"

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_has_allowed_tools(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        content = command_path.read_text(encoding="utf-8")
        assert "allowed-tools:" in content, f"{command_name} missing allowed-tools in frontmatter"

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_has_description(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        content = command_path.read_text(encoding="utf-8")
        assert "description:" in content, f"{command_name} missing description in frontmatter"

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_is_not_empty(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        content = command_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert len(body) > 50, f"{command_name} body is too short ({len(body)} chars)"

    @pytest.mark.parametrize("command_name", ALL_COMMANDS)
    def test_command_has_markdown_heading(self, command_name: str) -> None:
        command_path = COMMANDS_DIR / command_name
        content = command_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else ""
        assert "# " in body, f"{command_name} missing markdown heading in body"


class TestCommandContent:
    """Verify specific command content."""

    def test_catchup_reads_implementation_plan(self) -> None:
        content = (COMMANDS_DIR / "catchup.md").read_text(encoding="utf-8")
        assert "IMPLEMENTATION_PLAN" in content, "catchup should reference IMPLEMENTATION_PLAN.md"

    def test_catchup_reads_changelog(self) -> None:
        content = (COMMANDS_DIR / "catchup.md").read_text(encoding="utf-8")
        assert "CHANGELOG" in content, "catchup should reference CHANGELOG.md"

    def test_catchup_checks_git(self) -> None:
        content = (COMMANDS_DIR / "catchup.md").read_text(encoding="utf-8")
        assert "git log" in content, "catchup should analyze git history"

    def test_catchup_reads_vizier_docs(self) -> None:
        content = (COMMANDS_DIR / "catchup.md").read_text(encoding="utf-8")
        assert "ARCHITECTURE" in content, "catchup should reference ARCHITECTURE.md (Vizier-specific)"
        assert "DECISIONS" in content, "catchup should reference DECISIONS.md (Vizier-specific)"

    def test_security_audit_has_scoring(self) -> None:
        content = (COMMANDS_DIR / "security-audit.md").read_text(encoding="utf-8")
        assert "Grade" in content or "grade" in content, "security-audit should include grading"
        for grade in ["A", "B", "C", "D", "F"]:
            assert grade in content, f"security-audit missing grade: {grade}"

    def test_security_audit_checks_secrets(self) -> None:
        content = (COMMANDS_DIR / "security-audit.md").read_text(encoding="utf-8")
        assert "secret" in content.lower(), "security-audit should scan for secrets"

    def test_security_audit_checks_code_patterns(self) -> None:
        content = (COMMANDS_DIR / "security-audit.md").read_text(encoding="utf-8")
        for pattern in ["eval", "exec", "pickle", "subprocess"]:
            assert pattern in content, f"security-audit missing code pattern: {pattern}"
