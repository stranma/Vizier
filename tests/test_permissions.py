"""Validate .claude/settings.json structure, pattern syntax, and security invariants."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

SETTINGS_PATH = Path(__file__).resolve().parent.parent / ".claude" / "settings.json"


@pytest.fixture
def settings() -> dict:
    """Load and parse .claude/settings.json."""
    assert SETTINGS_PATH.exists(), f"Settings file not found: {SETTINGS_PATH}"
    return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def permissions(settings: dict) -> dict:
    """Extract the permissions block."""
    assert "permissions" in settings, "Missing 'permissions' key in settings"
    return settings["permissions"]


class TestJsonStructure:
    """Validate the JSON structure of settings.json."""

    def test_valid_json(self) -> None:
        content = SETTINGS_PATH.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_permissions_key_exists(self, settings: dict) -> None:
        assert "permissions" in settings

    def test_permission_lists_are_arrays(self, permissions: dict) -> None:
        for key in ("allow", "deny", "ask"):
            if key in permissions:
                assert isinstance(permissions[key], list), f"'{key}' must be a list"

    def test_all_entries_are_strings(self, permissions: dict) -> None:
        for key in ("allow", "deny", "ask"):
            for entry in permissions.get(key, []):
                assert isinstance(entry, str), f"Non-string entry in '{key}': {entry}"


class TestPatternSyntax:
    """Validate permission pattern syntax."""

    DEPRECATED_COLON_WILDCARD = re.compile(r":(\*|\.\*)\)")

    def test_no_deprecated_colon_wildcard(self, permissions: dict) -> None:
        """Ensure no entries use the deprecated :* syntax."""
        for key in ("allow", "deny", "ask"):
            for entry in permissions.get(key, []):
                assert not self.DEPRECATED_COLON_WILDCARD.search(entry), (
                    f"Deprecated ':*' syntax found in '{key}': {entry}. Use ' *' (space-wildcard) instead."
                )

    def test_bash_patterns_have_tool_prefix(self, permissions: dict) -> None:
        """All Bash patterns must start with 'Bash('."""
        for key in ("allow", "deny", "ask"):
            for entry in permissions.get(key, []):
                if "(" in entry:
                    assert entry.startswith("Bash(") or entry.startswith("WebFetch("), (
                        f"Unknown tool prefix in '{key}': {entry}"
                    )

    def test_patterns_are_balanced(self, permissions: dict) -> None:
        """Parentheses must be balanced in all patterns."""
        for key in ("allow", "deny", "ask"):
            for entry in permissions.get(key, []):
                open_count = entry.count("(")
                close_count = entry.count(")")
                assert open_count == close_count, f"Unbalanced parens in '{key}': {entry}"


class TestSecurityInvariants:
    """Validate security-critical permission rules."""

    def test_gh_secret_denied(self, permissions: dict) -> None:
        """gh secret commands must be in the deny list."""
        deny = permissions.get("deny", [])
        gh_secret_denied = any("gh secret" in entry for entry in deny)
        assert gh_secret_denied, "gh secret must be in the deny list"

    def test_gh_secret_not_allowed(self, permissions: dict) -> None:
        """gh secret commands must never appear in allow."""
        allow = permissions.get("allow", [])
        gh_secret_allowed = any("gh secret" in entry for entry in allow)
        assert not gh_secret_allowed, "gh secret must NOT be in the allow list"

    def test_webfetch_not_in_allow(self, permissions: dict) -> None:
        """WebFetch should require confirmation (ask), not be auto-allowed."""
        allow = permissions.get("allow", [])
        webfetch_allowed = any(entry == "WebFetch" or entry.startswith("WebFetch(") for entry in allow)
        assert not webfetch_allowed, "WebFetch must not be in 'allow' -- move to 'ask' for safety"

    def test_destructive_commands_not_allowed(self, permissions: dict) -> None:
        """Destructive commands should not be auto-allowed."""
        allow = permissions.get("allow", [])
        destructive_prefixes = ["Bash(docker ", "Bash(terraform ", "Bash(gh pr merge "]
        for entry in allow:
            for prefix in destructive_prefixes:
                assert not entry.startswith(prefix), f"Destructive command should be in 'ask', not 'allow': {entry}"


class TestEvaluationOrder:
    """Validate that deny/ask/allow lists don't have conflicting entries."""

    def _extract_command_prefix(self, entry: str) -> str:
        """Extract the command prefix (up to the wildcard) from a pattern for comparison."""
        if "(" in entry:
            inner = entry.split("(", 1)[1].rstrip(")")
            return inner.rstrip(" *").strip()
        return entry

    def test_deny_overrides_allow(self, permissions: dict) -> None:
        """Entries in deny should not also appear in allow with the same or more specific prefix."""
        deny_prefixes = [self._extract_command_prefix(e) for e in permissions.get("deny", [])]
        allow_prefixes = [self._extract_command_prefix(e) for e in permissions.get("allow", [])]
        conflicts = []
        for d in deny_prefixes:
            for a in allow_prefixes:
                if d == a or a.startswith(d + " ") or d.startswith(a + " "):
                    conflicts.append((d, a))
        assert not conflicts, f"Conflicting deny/allow prefixes (deny wins but this is confusing): {conflicts}"
