"""Tests for .claude/skills/ -- validates skill files exist and have correct structure."""

from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent / ".claude" / "skills"

ALL_SKILLS = [
    "sync",
    "design",
    "done",
    "edit-permissions",
]


class TestSkillExistence:
    """Verify all expected skill directories and files exist."""

    def test_skills_directory_exists(self) -> None:
        assert SKILLS_DIR.exists(), f"{SKILLS_DIR} does not exist"
        assert SKILLS_DIR.is_dir(), f"{SKILLS_DIR} is not a directory"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_directory_exists(self, skill_name: str) -> None:
        skill_dir = SKILLS_DIR / skill_name
        assert skill_dir.exists(), f"Skill directory missing: {skill_name}"
        assert skill_dir.is_dir(), f"{skill_name} is not a directory"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_file_exists(self, skill_name: str) -> None:
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_file.exists(), f"SKILL.md missing for: {skill_name}"


class TestSkillFrontmatter:
    """Verify skill files have correct YAML frontmatter."""

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_has_frontmatter(self, skill_name: str) -> None:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert content.startswith("---"), f"{skill_name} missing YAML frontmatter"
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"{skill_name} has unclosed frontmatter"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_has_name(self, skill_name: str) -> None:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert "name:" in content, f"{skill_name} missing name in frontmatter"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_has_description(self, skill_name: str) -> None:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        assert "description:" in content, f"{skill_name} missing description in frontmatter"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_body_not_empty(self, skill_name: str) -> None:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else ""
        assert len(body) > 50, f"{skill_name} body is too short ({len(body)} chars)"

    @pytest.mark.parametrize("skill_name", ALL_SKILLS)
    def test_skill_has_markdown_heading(self, skill_name: str) -> None:
        content = (SKILLS_DIR / skill_name / "SKILL.md").read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2] if len(parts) >= 3 else ""
        assert "# " in body, f"{skill_name} missing markdown heading in body"


class TestSkillContent:
    """Verify specific skill content."""

    def test_sync_is_read_only(self) -> None:
        content = (SKILLS_DIR / "sync" / "SKILL.md").read_text(encoding="utf-8")
        assert "read-only" in content.lower(), "sync should be read-only"

    def test_sync_checks_branch(self) -> None:
        content = (SKILLS_DIR / "sync" / "SKILL.md").read_text(encoding="utf-8")
        assert "branch" in content.lower(), "sync should check branch state"

    def test_sync_checks_remote(self) -> None:
        content = (SKILLS_DIR / "sync" / "SKILL.md").read_text(encoding="utf-8")
        assert "remote" in content.lower(), "sync should check remote tracking"

    def test_design_reads_decisions(self) -> None:
        content = (SKILLS_DIR / "design" / "SKILL.md").read_text(encoding="utf-8")
        assert "DECISIONS" in content, "design should reference DECISIONS.md"

    def test_design_classifies_scope(self) -> None:
        content = (SKILLS_DIR / "design" / "SKILL.md").read_text(encoding="utf-8")
        for scope in ["Q", "S", "P"]:
            assert f"**{scope}**" in content, f"design should reference scope {scope}"

    def test_design_uses_plan_mode(self) -> None:
        content = (SKILLS_DIR / "design" / "SKILL.md").read_text(encoding="utf-8")
        assert "EnterPlanMode" in content, "design should use EnterPlanMode for S and P scope"

    def test_done_detects_scope(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "Detect scope" in content or "detect scope" in content, "done should auto-detect scope"

    def test_done_has_three_tiers(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "Blocker" in content, "done should have Blockers tier"
        assert "High Priority" in content, "done should have High Priority tier"
        assert "Recommended" in content, "done should have Recommended tier"

    def test_done_checks_tests(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "pytest" in content, "done should run tests"

    def test_done_checks_lint(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "ruff" in content, "done should check linting"

    def test_done_checks_types(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "pyright" in content, "done should check types"

    def test_done_references_agents(self) -> None:
        content = (SKILLS_DIR / "done" / "SKILL.md").read_text(encoding="utf-8")
        assert "pr-writer" in content, "done should reference pr-writer agent"
        assert "code-reviewer" in content, "done should reference code-reviewer agent"
        assert "docs-updater" in content, "done should reference docs-updater agent"

    def test_edit_permissions_has_pattern_syntax(self) -> None:
        content = (SKILLS_DIR / "edit-permissions" / "SKILL.md").read_text(encoding="utf-8")
        assert "pattern" in content.lower(), "edit-permissions should document pattern syntax"

    def test_edit_permissions_has_safety_rules(self) -> None:
        content = (SKILLS_DIR / "edit-permissions" / "SKILL.md").read_text(encoding="utf-8")
        assert "Safety" in content or "safety" in content, "edit-permissions should have safety rules"
