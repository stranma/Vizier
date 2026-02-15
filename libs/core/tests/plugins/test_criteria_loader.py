"""Tests for criteria library loader."""

from vizier.core.plugins.criteria_loader import CriteriaLibraryLoader


class TestCriteriaLibraryLoader:
    def test_load_from_directory(self, tmp_path) -> None:
        criteria_dir = tmp_path / "criteria"
        criteria_dir.mkdir()
        (criteria_dir / "tests_pass.md").write_text("All tests must pass.", encoding="utf-8")
        (criteria_dir / "lint_clean.md").write_text("Code must pass linting.", encoding="utf-8")

        loader = CriteriaLibraryLoader(criteria_dir)
        library = loader.load()
        assert len(library) == 2
        assert library["tests_pass"] == "All tests must pass."
        assert library["lint_clean"] == "Code must pass linting."

    def test_get_single_criterion(self, tmp_path) -> None:
        criteria_dir = tmp_path / "criteria"
        criteria_dir.mkdir()
        (criteria_dir / "tests_pass.md").write_text("All tests must pass.", encoding="utf-8")

        loader = CriteriaLibraryLoader(criteria_dir)
        assert loader.get("tests_pass") == "All tests must pass."

    def test_get_nonexistent_returns_none(self, tmp_path) -> None:
        criteria_dir = tmp_path / "criteria"
        criteria_dir.mkdir()

        loader = CriteriaLibraryLoader(criteria_dir)
        assert loader.get("nonexistent") is None

    def test_load_empty_directory(self, tmp_path) -> None:
        criteria_dir = tmp_path / "criteria"
        criteria_dir.mkdir()

        loader = CriteriaLibraryLoader(criteria_dir)
        assert loader.load() == {}

    def test_load_nonexistent_directory(self, tmp_path) -> None:
        loader = CriteriaLibraryLoader(tmp_path / "nonexistent")
        assert loader.load() == {}
