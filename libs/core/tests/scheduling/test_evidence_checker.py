"""Tests for evidence completeness checker (D56)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.scheduling.evidence_checker import (
    EVIDENCE_TYPES_DOCUMENTS,
    EVIDENCE_TYPES_SOFTWARE,
    EvidenceChecker,
    get_required_evidence,
)


class TestEvidenceChecker:
    def test_all_present(self, tmp_path: Path) -> None:
        for ev in EVIDENCE_TYPES_SOFTWARE:
            (tmp_path / f"{ev}.txt").write_text("evidence")
        checker = EvidenceChecker(EVIDENCE_TYPES_SOFTWARE, str(tmp_path))
        result = checker.check()
        assert result.complete is True
        assert result.missing == []
        assert len(result.found) == 4

    def test_some_missing(self, tmp_path: Path) -> None:
        (tmp_path / "test_output.txt").write_text("PASSED")
        (tmp_path / "lint_output.txt").write_text("clean")
        checker = EvidenceChecker(EVIDENCE_TYPES_SOFTWARE, str(tmp_path))
        result = checker.check()
        assert result.complete is False
        assert "type_check_output" in result.missing
        assert "diff" in result.missing
        assert "test_output" in result.found
        assert "lint_output" in result.found

    def test_all_missing(self, tmp_path: Path) -> None:
        checker = EvidenceChecker(EVIDENCE_TYPES_SOFTWARE, str(tmp_path))
        result = checker.check()
        assert result.complete is False
        assert len(result.missing) == 4

    def test_nonexistent_directory(self) -> None:
        checker = EvidenceChecker(["test_output"], "/nonexistent/path/12345")
        result = checker.check()
        assert result.complete is False
        assert result.missing == ["test_output"]

    def test_empty_required(self, tmp_path: Path) -> None:
        checker = EvidenceChecker([], str(tmp_path))
        result = checker.check()
        assert result.complete is True
        assert result.missing == []

    def test_documents_evidence(self, tmp_path: Path) -> None:
        for ev in EVIDENCE_TYPES_DOCUMENTS:
            (tmp_path / f"{ev}.txt").write_text("ok")
        checker = EvidenceChecker(EVIDENCE_TYPES_DOCUMENTS, str(tmp_path))
        result = checker.check()
        assert result.complete is True

    def test_different_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "test_output.log").write_text("PASSED")
        (tmp_path / "lint_output.json").write_text("{}")
        checker = EvidenceChecker(["test_output", "lint_output"], str(tmp_path))
        result = checker.check()
        assert result.complete is True

    def test_required_types_property(self) -> None:
        checker = EvidenceChecker(["a", "b", "c"], "/tmp")
        assert checker.required_types == ["a", "b", "c"]


class TestGetRequiredEvidence:
    def test_software_plugin(self) -> None:
        result = get_required_evidence("software")
        assert result == EVIDENCE_TYPES_SOFTWARE

    def test_documents_plugin(self) -> None:
        result = get_required_evidence("documents")
        assert result == EVIDENCE_TYPES_DOCUMENTS

    def test_unknown_plugin(self) -> None:
        result = get_required_evidence("unknown")
        assert result == []
