"""Tests for .claude/hooks/ -- validates hook scripts exist, are executable, and have correct structure."""

import stat
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).parent.parent / ".claude" / "hooks"

SECURITY_HOOKS = [
    "dangerous-actions-blocker.sh",
    "output-secrets-scanner.sh",
    "unicode-injection-scanner.sh",
]

PRODUCTIVITY_HOOKS = [
    "auto-format.sh",
    "test-on-change.sh",
]

ALL_HOOKS = SECURITY_HOOKS + PRODUCTIVITY_HOOKS


class TestHookExistence:
    """Verify all expected hook scripts exist."""

    def test_hooks_directory_exists(self) -> None:
        assert HOOKS_DIR.exists(), f"{HOOKS_DIR} does not exist"
        assert HOOKS_DIR.is_dir(), f"{HOOKS_DIR} is not a directory"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_file_exists(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        assert hook_path.exists(), f"Hook script missing: {hook_name}"

    def test_no_unexpected_hooks(self) -> None:
        actual_hooks = {f.name for f in HOOKS_DIR.iterdir() if f.is_file() and f.suffix == ".sh"}
        expected_hooks = set(ALL_HOOKS)
        unexpected = actual_hooks - expected_hooks
        assert not unexpected, f"Unexpected hook scripts found: {unexpected}"


class TestHookPermissions:
    """Verify all hook scripts are executable."""

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_is_executable(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{hook_name} is not executable (missing user execute bit)"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_is_readable(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        mode = hook_path.stat().st_mode
        assert mode & stat.S_IRUSR, f"{hook_name} is not readable"


class TestHookStructure:
    """Verify hook scripts have correct structure."""

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_has_shebang(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        first_line = hook_path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line == "#!/bin/bash", f"{hook_name} missing #!/bin/bash shebang, got: {first_line!r}"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_has_description_comment(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        content = hook_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        comment_lines = [line for line in lines[1:10] if line.startswith("#")]
        assert len(comment_lines) >= 1, f"{hook_name} missing description comment after shebang"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_uses_jq(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        content = hook_path.read_text(encoding="utf-8")
        assert "jq" in content, f"{hook_name} does not use jq for JSON parsing"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_handles_missing_jq(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        content = hook_path.read_text(encoding="utf-8")
        assert "command -v jq" in content, f"{hook_name} does not check for jq availability"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_ends_with_exit_0(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        content = hook_path.read_text(encoding="utf-8").rstrip()
        assert content.endswith("exit 0"), f"{hook_name} does not end with 'exit 0'"

    @pytest.mark.parametrize("hook_name", ALL_HOOKS)
    def test_hook_is_not_empty(self, hook_name: str) -> None:
        hook_path = HOOKS_DIR / hook_name
        content = hook_path.read_text(encoding="utf-8")
        assert len(content) > 100, f"{hook_name} appears to be too short ({len(content)} bytes)"


class TestSecurityHookBehavior:
    """Verify security hooks have the correct blocking/warning patterns."""

    def test_dangerous_actions_blocker_exits_2_for_blocks(self) -> None:
        content = (HOOKS_DIR / "dangerous-actions-blocker.sh").read_text(encoding="utf-8")
        assert "exit 2" in content, "dangerous-actions-blocker must exit 2 to block actions"

    def test_dangerous_actions_blocker_checks_bash_only(self) -> None:
        content = (HOOKS_DIR / "dangerous-actions-blocker.sh").read_text(encoding="utf-8")
        assert '"Bash"' in content, "dangerous-actions-blocker should only check Bash tool"

    def test_dangerous_actions_blocker_has_blocked_patterns(self) -> None:
        content = (HOOKS_DIR / "dangerous-actions-blocker.sh").read_text(encoding="utf-8")
        for pattern in ["rm -rf", "DROP DATABASE", "git push --force"]:
            assert pattern in content, f"dangerous-actions-blocker missing pattern: {pattern}"

    def test_dangerous_actions_blocker_checks_secrets(self) -> None:
        content = (HOOKS_DIR / "dangerous-actions-blocker.sh").read_text(encoding="utf-8")
        for pattern in ["ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY"]:
            assert pattern in content, f"dangerous-actions-blocker missing secret pattern: {pattern}"

    def test_unicode_scanner_exits_2_for_blocks(self) -> None:
        content = (HOOKS_DIR / "unicode-injection-scanner.sh").read_text(encoding="utf-8")
        assert "exit 2" in content, "unicode-injection-scanner must exit 2 to block actions"

    def test_unicode_scanner_checks_edit_and_write(self) -> None:
        content = (HOOKS_DIR / "unicode-injection-scanner.sh").read_text(encoding="utf-8")
        assert '"Edit"' in content, "unicode-injection-scanner should check Edit tool"
        assert '"Write"' in content, "unicode-injection-scanner should check Write tool"

    def test_unicode_scanner_detects_zero_width_chars(self) -> None:
        content = (HOOKS_DIR / "unicode-injection-scanner.sh").read_text(encoding="utf-8")
        assert "200B" in content, "unicode-injection-scanner should detect zero-width space (U+200B)"

    def test_unicode_scanner_detects_rtl_override(self) -> None:
        content = (HOOKS_DIR / "unicode-injection-scanner.sh").read_text(encoding="utf-8")
        assert "202A" in content or "202E" in content, "unicode-injection-scanner should detect RTL override"

    def test_unicode_scanner_detects_ansi_escapes(self) -> None:
        content = (HOOKS_DIR / "unicode-injection-scanner.sh").read_text(encoding="utf-8")
        assert "ANSI" in content, "unicode-injection-scanner should detect ANSI escape sequences"

    def test_output_secrets_scanner_never_blocks(self) -> None:
        content = (HOOKS_DIR / "output-secrets-scanner.sh").read_text(encoding="utf-8")
        assert "exit 2" not in content, "output-secrets-scanner (PostToolUse) must never exit 2"

    def test_output_secrets_scanner_emits_system_message(self) -> None:
        content = (HOOKS_DIR / "output-secrets-scanner.sh").read_text(encoding="utf-8")
        assert "systemMessage" in content, "output-secrets-scanner should emit systemMessage for warnings"

    def test_output_secrets_scanner_detects_key_patterns(self) -> None:
        content = (HOOKS_DIR / "output-secrets-scanner.sh").read_text(encoding="utf-8")
        for pattern in ["AKIA", "sk-ant-", "ghp_", "PRIVATE KEY"]:
            assert pattern in content, f"output-secrets-scanner missing pattern: {pattern}"


class TestProductivityHookBehavior:
    """Verify productivity hooks have correct patterns."""

    def test_auto_format_targets_python_files(self) -> None:
        content = (HOOKS_DIR / "auto-format.sh").read_text(encoding="utf-8")
        assert "*.py" in content or ".py" in content, "auto-format should target Python files"

    def test_auto_format_uses_ruff(self) -> None:
        content = (HOOKS_DIR / "auto-format.sh").read_text(encoding="utf-8")
        assert "ruff format" in content, "auto-format should use ruff format"
        assert "ruff check --fix" in content, "auto-format should use ruff check --fix"

    def test_auto_format_checks_edit_and_write(self) -> None:
        content = (HOOKS_DIR / "auto-format.sh").read_text(encoding="utf-8")
        assert '"Edit"' in content, "auto-format should check Edit tool"
        assert '"Write"' in content, "auto-format should check Write tool"

    def test_test_on_change_discovers_test_files(self) -> None:
        content = (HOOKS_DIR / "test-on-change.sh").read_text(encoding="utf-8")
        assert "test_" in content, "test-on-change should discover test_ prefixed files"

    def test_test_on_change_uses_pytest(self) -> None:
        content = (HOOKS_DIR / "test-on-change.sh").read_text(encoding="utf-8")
        assert "pytest" in content, "test-on-change should use pytest"

    def test_test_on_change_never_blocks(self) -> None:
        content = (HOOKS_DIR / "test-on-change.sh").read_text(encoding="utf-8")
        assert "exit 2" not in content, "test-on-change should never block (informational only)"

    def test_test_on_change_emits_system_message_on_failure(self) -> None:
        content = (HOOKS_DIR / "test-on-change.sh").read_text(encoding="utf-8")
        assert "systemMessage" in content, "test-on-change should emit systemMessage for test failures"
