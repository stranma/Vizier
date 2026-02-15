"""Tests for criteria reference resolution and snapshotting."""

from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria

SAMPLE_LIBRARY = {
    "tests_pass": "All tests related to this spec must pass. Run the test command and verify exit code 0.",
    "lint_clean": "Code must pass all linting rules. Run `uv run ruff check` and verify exit code 0.",
    "type_check": "Code must pass type checking. Run `uv run pyright` and verify exit code 0.",
}


class TestResolveCriteriaReferences:
    def test_finds_single_reference(self) -> None:
        content = "- [ ] @criteria/tests_pass: `uv run pytest`"
        refs = resolve_criteria_references(content)
        assert refs == ["tests_pass"]

    def test_finds_multiple_references(self) -> None:
        content = (
            "- [ ] @criteria/tests_pass: run tests\n"
            "- [ ] @criteria/lint_clean: lint check\n"
            "- [ ] Custom criterion\n"
            "- [ ] @criteria/type_check: type check\n"
        )
        refs = resolve_criteria_references(content)
        assert refs == ["tests_pass", "lint_clean", "type_check"]

    def test_no_references(self) -> None:
        content = "- [ ] All tests must pass\n- [ ] Code must lint"
        refs = resolve_criteria_references(content)
        assert refs == []

    def test_empty_content(self) -> None:
        refs = resolve_criteria_references("")
        assert refs == []


class TestSnapshotCriteria:
    def test_snapshots_single_reference(self) -> None:
        content = "- [ ] @criteria/tests_pass"
        result = snapshot_criteria(content, SAMPLE_LIBRARY)
        assert "<!-- snapshot: tests_pass -->" in result
        assert "All tests related to this spec must pass" in result
        assert "<!-- /snapshot -->" in result

    def test_snapshots_multiple_references(self) -> None:
        content = "- [ ] @criteria/tests_pass\n- [ ] @criteria/lint_clean"
        result = snapshot_criteria(content, SAMPLE_LIBRARY)
        assert "<!-- snapshot: tests_pass -->" in result
        assert "<!-- snapshot: lint_clean -->" in result

    def test_unknown_reference_unchanged(self) -> None:
        content = "- [ ] @criteria/unknown_criterion"
        result = snapshot_criteria(content, SAMPLE_LIBRARY)
        assert result == content

    def test_no_references_unchanged(self) -> None:
        content = "No criteria references here."
        result = snapshot_criteria(content, SAMPLE_LIBRARY)
        assert result == content

    def test_mixed_known_and_unknown(self) -> None:
        content = "- [ ] @criteria/tests_pass\n- [ ] @criteria/nonexistent"
        result = snapshot_criteria(content, SAMPLE_LIBRARY)
        assert "<!-- snapshot: tests_pass -->" in result
        assert "@criteria/nonexistent" in result
        assert "<!-- snapshot: nonexistent -->" not in result
