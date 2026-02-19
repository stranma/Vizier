"""Tests for write-set enforcement (D55)."""

from vizier.core.tools.domain.write_set import WriteSetChecker


class TestWriteSetChecker:
    def test_empty_patterns_allows_everything(self) -> None:
        checker = WriteSetChecker([])
        assert checker.is_allowed("anything/goes.py")

    def test_exact_pattern(self) -> None:
        checker = WriteSetChecker(["pyproject.toml"])
        assert checker.is_allowed("pyproject.toml")
        assert not checker.is_allowed("other.toml")

    def test_star_pattern(self) -> None:
        checker = WriteSetChecker(["*.py"])
        assert checker.is_allowed("main.py")
        assert not checker.is_allowed("main.js")

    def test_directory_star(self) -> None:
        checker = WriteSetChecker(["src/*.py"])
        assert checker.is_allowed("src/main.py")
        assert not checker.is_allowed("src/sub/main.py")

    def test_double_star_recursive(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"])
        assert checker.is_allowed("src/main.py")
        assert checker.is_allowed("src/sub/deep/main.py")
        assert not checker.is_allowed("tests/main.py")

    def test_multiple_patterns(self) -> None:
        checker = WriteSetChecker(["src/**/*.py", "tests/**/*.py", "docs/**/*.md"])
        assert checker.is_allowed("src/core/engine.py")
        assert checker.is_allowed("tests/test_engine.py")
        assert checker.is_allowed("docs/design/arch.md")
        assert not checker.is_allowed("config/settings.yaml")

    def test_absolute_path_with_root(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"], project_root="/home/user/project")
        assert checker.is_allowed("/home/user/project/src/main.py")
        assert not checker.is_allowed("/home/user/other/src/main.py")

    def test_windows_paths(self) -> None:
        checker = WriteSetChecker(["src/**/*.py"], project_root="C:\\my_source\\Project")
        assert checker.is_allowed("C:\\my_source\\Project\\src\\main.py")

    def test_patterns_property(self) -> None:
        patterns = ["src/**", "tests/**"]
        checker = WriteSetChecker(patterns)
        result = checker.patterns
        assert result == patterns
        result.clear()
        assert checker.patterns == patterns
