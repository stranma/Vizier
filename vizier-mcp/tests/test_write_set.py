"""Tests for WriteSetChecker (AC-S2)."""

from __future__ import annotations

from vizier_mcp.sentinel.write_set import WriteSetChecker


class TestWriteSetChecker:
    """Tests for glob pattern matching on file paths."""

    def test_empty_patterns_allows_all(self) -> None:
        checker = WriteSetChecker([])
        assert checker.is_allowed("anything/goes.py") is True

    def test_star_matches_single_segment(self) -> None:
        checker = WriteSetChecker(["src/*.py"])
        assert checker.is_allowed("src/auth.py") is True
        assert checker.is_allowed("src/deep/auth.py") is False

    def test_double_star_matches_recursive(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        assert checker.is_allowed("src/auth.py") is True
        assert checker.is_allowed("src/deep/auth.py") is True
        assert checker.is_allowed("src/a/b/c/auth.py") is True

    def test_question_mark_matches_single_char(self) -> None:
        checker = WriteSetChecker(["src/?.py"])
        assert checker.is_allowed("src/a.py") is True
        assert checker.is_allowed("src/ab.py") is False

    def test_no_match(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        assert checker.is_allowed("docs/readme.md") is False

    def test_multiple_patterns(self) -> None:
        checker = WriteSetChecker(["src/**/*.py", "tests/**/*.py", "docs/**/*.md"])
        assert checker.is_allowed("src/main.py") is True
        assert checker.is_allowed("tests/test_main.py") is True
        assert checker.is_allowed("docs/guide.md") is True
        assert checker.is_allowed("config.yaml") is False

    def test_exact_file_match(self) -> None:
        checker = WriteSetChecker(["pyproject.toml"])
        assert checker.is_allowed("pyproject.toml") is True
        assert checker.is_allowed("other.toml") is False

    def test_leading_slash_stripped(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        assert checker.is_allowed("/src/auth.py") is True

    def test_leading_dot_slash_stripped(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        assert checker.is_allowed("./src/auth.py") is True

    def test_double_star_at_start(self) -> None:
        checker = WriteSetChecker(["**/*.py"])
        assert checker.is_allowed("anything.py") is True
        assert checker.is_allowed("deep/nested/file.py") is True
        assert checker.is_allowed("file.txt") is False

    def test_special_regex_chars_escaped(self) -> None:
        checker = WriteSetChecker(["src/file.name+extra.py"])
        assert checker.is_allowed("src/file.name+extra.py") is True
        assert checker.is_allowed("src/fileXnameXextra.py") is False
