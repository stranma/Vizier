"""Tests for .claude/rules/ -- validates rule files exist and have correct structure."""

from pathlib import Path

import pytest

RULES_DIR = Path(__file__).parent.parent / ".claude" / "rules"

ALL_RULES = [
    "architecture-review.md",
    "code-quality-review.md",
    "performance-review.md",
    "test-review.md",
]


class TestRuleExistence:
    """Verify all expected rule files exist."""

    def test_rules_directory_exists(self) -> None:
        assert RULES_DIR.exists(), f"{RULES_DIR} does not exist"
        assert RULES_DIR.is_dir(), f"{RULES_DIR} is not a directory"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_file_exists(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        assert rule_path.exists(), f"Rule file missing: {rule_name}"


class TestRuleStructure:
    """Verify rule files have correct frontmatter and content."""

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_has_frontmatter(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{rule_name} missing YAML frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{rule_name} has unclosed frontmatter"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_has_description(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        assert "description:" in content, f"{rule_name} missing description in frontmatter"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_has_no_paths_field(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        frontmatter = parts[1] if len(parts) >= 3 else ""
        assert "paths:" not in frontmatter, f"{rule_name} should not have paths: field (rules apply globally)"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_is_not_empty(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert len(body) > 100, f"{rule_name} body is too short ({len(body)} chars)"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_has_heading(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else ""
        assert "# " in body, f"{rule_name} missing markdown heading"

    @pytest.mark.parametrize("rule_name", ALL_RULES)
    def test_rule_is_concise(self, rule_name: str) -> None:
        rule_path = RULES_DIR / rule_name
        content = rule_path.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        assert line_count <= 80, f"{rule_name} is too long ({line_count} lines, max 80)"


class TestRuleContent:
    """Verify rules cover expected review dimensions."""

    def test_architecture_review_covers_dependencies(self) -> None:
        content = (RULES_DIR / "architecture-review.md").read_text(encoding="utf-8")
        assert "Dependencies" in content or "dependencies" in content

    def test_architecture_review_covers_security(self) -> None:
        content = (RULES_DIR / "architecture-review.md").read_text(encoding="utf-8")
        assert "Security" in content or "security" in content

    def test_code_quality_review_covers_dry(self) -> None:
        content = (RULES_DIR / "code-quality-review.md").read_text(encoding="utf-8")
        assert "DRY" in content or "duplication" in content.lower()

    def test_code_quality_review_covers_error_handling(self) -> None:
        content = (RULES_DIR / "code-quality-review.md").read_text(encoding="utf-8")
        assert "Error" in content or "error" in content

    def test_code_quality_review_covers_type_annotations(self) -> None:
        content = (RULES_DIR / "code-quality-review.md").read_text(encoding="utf-8")
        assert "Type" in content or "type" in content

    def test_performance_review_covers_n_plus_1(self) -> None:
        content = (RULES_DIR / "performance-review.md").read_text(encoding="utf-8")
        assert "N+1" in content

    def test_performance_review_covers_caching(self) -> None:
        content = (RULES_DIR / "performance-review.md").read_text(encoding="utf-8")
        assert "Caching" in content or "caching" in content

    def test_performance_review_covers_complexity(self) -> None:
        content = (RULES_DIR / "performance-review.md").read_text(encoding="utf-8")
        assert "O(n" in content or "complexity" in content.lower()

    def test_test_review_covers_coverage(self) -> None:
        content = (RULES_DIR / "test-review.md").read_text(encoding="utf-8")
        assert "Coverage" in content or "coverage" in content

    def test_test_review_covers_edge_cases(self) -> None:
        content = (RULES_DIR / "test-review.md").read_text(encoding="utf-8")
        assert "Edge" in content or "edge" in content

    def test_test_review_covers_isolation(self) -> None:
        content = (RULES_DIR / "test-review.md").read_text(encoding="utf-8")
        assert "Isolation" in content or "isolation" in content or "independent" in content.lower()

    def test_test_review_covers_assertion_quality(self) -> None:
        content = (RULES_DIR / "test-review.md").read_text(encoding="utf-8")
        assert "Assertion" in content or "assertion" in content
