"""Tests for spec file I/O operations."""

from __future__ import annotations

import pytest

from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.models.spec import SpecComplexity, SpecStatus


@pytest.fixture
def project_root(tmp_path):
    vizier_dir = tmp_path / ".vizier" / "specs"
    vizier_dir.mkdir(parents=True)
    return tmp_path


class TestCreateSpec:
    def test_creates_spec_file(self, project_root) -> None:
        spec = create_spec(project_root, "001-test-feature", "# Test Feature\n\nRequirements here.")
        assert spec.frontmatter.id == "001-test-feature"
        assert spec.frontmatter.status == SpecStatus.DRAFT
        assert spec.content == "# Test Feature\n\nRequirements here."
        assert spec.file_path is not None
        assert "001-test-feature" in spec.file_path

    def test_creates_directory_structure(self, project_root) -> None:
        create_spec(project_root, "001-test", "content")
        spec_dir = project_root / ".vizier" / "specs" / "001-test"
        assert spec_dir.exists()
        assert (spec_dir / "spec.md").exists()

    def test_with_frontmatter_overrides(self, project_root) -> None:
        spec = create_spec(
            project_root,
            "002-auth",
            "# Auth",
            frontmatter_overrides={"priority": 2, "complexity": "high", "plugin": "documents"},
        )
        assert spec.frontmatter.priority == 2
        assert spec.frontmatter.complexity == SpecComplexity.HIGH
        assert spec.frontmatter.plugin == "documents"

    def test_file_content_roundtrips(self, project_root) -> None:
        content = "# Test\n\n## Requirements\n\n- MUST do X\n- MUST do Y"
        spec = create_spec(project_root, "001-test", content)
        assert spec.file_path is not None
        reread = read_spec(spec.file_path)
        assert reread.content.strip() == content.strip()
        assert reread.frontmatter.id == "001-test"


class TestReadSpec:
    def test_reads_existing_spec(self, project_root) -> None:
        created = create_spec(project_root, "001-read-test", "# Read Test")
        assert created.file_path is not None
        spec = read_spec(created.file_path)
        assert spec.frontmatter.id == "001-read-test"

    def test_raises_on_missing_file(self) -> None:
        with pytest.raises(FileNotFoundError):
            read_spec("/nonexistent/path/spec.md")


class TestUpdateSpecStatus:
    def test_valid_transition(self, project_root) -> None:
        spec = create_spec(project_root, "001-update", "content")
        assert spec.file_path is not None
        updated = update_spec_status(spec.file_path, SpecStatus.READY)
        assert updated.frontmatter.status == SpecStatus.READY

    def test_invalid_transition_raises(self, project_root) -> None:
        spec = create_spec(project_root, "001-invalid", "content")
        assert spec.file_path is not None
        with pytest.raises(ValueError, match="Invalid transition"):
            update_spec_status(spec.file_path, SpecStatus.DONE)

    def test_extra_updates(self, project_root) -> None:
        spec = create_spec(project_root, "001-extra", "content")
        assert spec.file_path is not None
        updated = update_spec_status(
            spec.file_path,
            SpecStatus.READY,
            extra_updates={"priority": 3},
        )
        assert updated.frontmatter.status == SpecStatus.READY
        assert updated.frontmatter.priority == 3

    def test_full_lifecycle(self, project_root) -> None:
        spec = create_spec(project_root, "001-lifecycle", "content")
        assert spec.file_path is not None
        path = spec.file_path
        spec = update_spec_status(path, SpecStatus.READY)
        spec = update_spec_status(path, SpecStatus.IN_PROGRESS, extra_updates={"assigned_to": "worker-1"})
        assert spec.frontmatter.assigned_to == "worker-1"
        spec = update_spec_status(path, SpecStatus.REVIEW)
        spec = update_spec_status(path, SpecStatus.DONE)
        assert spec.frontmatter.status == SpecStatus.DONE

    def test_rejection_cycle(self, project_root) -> None:
        spec = create_spec(project_root, "001-reject", "content")
        assert spec.file_path is not None
        path = spec.file_path
        update_spec_status(path, SpecStatus.READY)
        update_spec_status(path, SpecStatus.IN_PROGRESS)
        update_spec_status(path, SpecStatus.REVIEW)
        spec = update_spec_status(path, SpecStatus.REJECTED)
        assert spec.frontmatter.status == SpecStatus.REJECTED
        spec = update_spec_status(path, SpecStatus.IN_PROGRESS, extra_updates={"retries": 1})
        assert spec.frontmatter.retries == 1


class TestAtomicWrites:
    def test_create_spec_no_tmp_file_left(self, project_root) -> None:
        create_spec(project_root, "001-atomic", "# Atomic Test")
        spec_dir = project_root / ".vizier" / "specs" / "001-atomic"
        tmp_files = list(spec_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover .tmp files found: {tmp_files}"

    def test_update_status_no_tmp_file_left(self, project_root) -> None:
        spec = create_spec(project_root, "001-update-atomic", "content")
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.READY)
        spec_dir = project_root / ".vizier" / "specs" / "001-update-atomic"
        tmp_files = list(spec_dir.glob("*.tmp"))
        assert tmp_files == [], f"Leftover .tmp files found: {tmp_files}"

    def test_original_file_survives_if_stale_tmp_exists(self, project_root) -> None:
        spec_dir = project_root / ".vizier" / "specs" / "001-stale-tmp"
        spec_dir.mkdir(parents=True, exist_ok=True)
        stale_tmp = spec_dir / "spec.md.tmp"
        stale_tmp.write_text("stale temporary content", encoding="utf-8")
        spec = create_spec(project_root, "001-stale-tmp", "# Fresh Content")
        assert spec.frontmatter.id == "001-stale-tmp"
        assert spec.content == "# Fresh Content"
        tmp_files = list(spec_dir.glob("*.tmp"))
        assert tmp_files == [], f"Stale .tmp file not cleaned up: {tmp_files}"


class TestListSpecs:
    def test_empty_project(self, project_root) -> None:
        specs = list_specs(project_root)
        assert specs == []

    def test_lists_all_specs(self, project_root) -> None:
        create_spec(project_root, "001-first", "First")
        create_spec(project_root, "002-second", "Second")
        specs = list_specs(project_root)
        ids = {s.frontmatter.id for s in specs}
        assert ids == {"001-first", "002-second"}

    def test_filter_by_status(self, project_root) -> None:
        create_spec(project_root, "001-draft", "Draft")
        spec2 = create_spec(project_root, "002-ready", "Ready")
        assert spec2.file_path is not None
        update_spec_status(spec2.file_path, SpecStatus.READY)

        drafts = list_specs(project_root, status_filter=SpecStatus.DRAFT)
        assert len(drafts) == 1
        assert drafts[0].frontmatter.id == "001-draft"

        ready = list_specs(project_root, status_filter=SpecStatus.READY)
        assert len(ready) == 1
        assert ready[0].frontmatter.id == "002-ready"

    def test_nonexistent_specs_dir(self, tmp_path) -> None:
        specs = list_specs(tmp_path)
        assert specs == []
