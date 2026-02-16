"""Tests for Scout research report."""

from __future__ import annotations

from vizier.core.scout.report import ResearchReport, build_report, read_report, write_report
from vizier.core.scout.sources import SearchResult


class TestBuildReport:
    def test_renders_markdown_with_solutions(self) -> None:
        report = ResearchReport(
            spec_id="001-add-auth",
            decision="RESEARCH",
            summary="Found several auth libraries.",
            recommendation="USE_LIBRARY",
            solutions=[
                SearchResult(
                    name="authlib",
                    url="https://github.com/lepture/authlib",
                    source="github",
                    description="OAuth/OIDC library",
                    license="BSD-3-Clause",
                    metric="4000 stars",
                    relevance="HIGH",
                ),
            ],
            queries=["python auth library", "oauth2 python"],
        )
        md = build_report(report)
        assert "# Prior Art Research: 001-add-auth" in md
        assert "Found several auth libraries." in md
        assert "USE_LIBRARY" in md
        assert "### authlib" in md
        assert "BSD-3-Clause" in md
        assert "4000 stars" in md
        assert "- python auth library" in md

    def test_renders_empty_report(self) -> None:
        report = ResearchReport(
            spec_id="002-fix-bug",
            decision="SKIP",
        )
        md = build_report(report)
        assert "# Prior Art Research: 002-fix-bug" in md
        assert "No research performed." in md
        assert "BUILD_FROM_SCRATCH" in md
        assert "## Existing Solutions" not in md

    def test_renders_report_without_license(self) -> None:
        report = ResearchReport(
            spec_id="003",
            decision="RESEARCH",
            summary="Found one package.",
            solutions=[
                SearchResult(name="pkg", url="https://example.com", source="npm"),
            ],
        )
        md = build_report(report)
        assert "**License:**" not in md


class TestWriteAndRead:
    def test_roundtrip(self, tmp_path: object) -> None:
        from pathlib import Path

        spec_dir = str(tmp_path)  # type: ignore[arg-type]
        report = ResearchReport(
            spec_id="001-test",
            decision="RESEARCH",
            summary="Test report.",
            recommendation="BUILD_FROM_SCRATCH",
            queries=["test query"],
        )
        path = write_report(spec_dir, report)
        assert Path(path).exists()

        content = read_report(spec_dir)
        assert content is not None
        assert "# Prior Art Research: 001-test" in content
        assert "Test report." in content

    def test_read_nonexistent_returns_none(self, tmp_path: object) -> None:
        result = read_report(str(tmp_path))  # type: ignore[arg-type]
        assert result is None

    def test_write_creates_parent_dirs(self, tmp_path: object) -> None:
        from pathlib import Path

        spec_dir = str(Path(str(tmp_path)) / "deep" / "nested" / "dir")  # type: ignore[arg-type]
        report = ResearchReport(spec_id="nested", decision="SKIP")
        path = write_report(spec_dir, report)
        assert Path(path).exists()
