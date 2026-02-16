"""Tests for CLI spec commands."""

from __future__ import annotations

from typing import Any

import pytest
from click.testing import CliRunner

from vizier.cli import main
from vizier.core.file_protocol.spec_io import create_spec, list_specs
from vizier.core.models.spec import SpecStatus


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier" / "specs"
    vizier_dir.mkdir(parents=True)
    return str(tmp_path)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestSpecCreate:
    def test_creates_draft_spec(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "create", "Build authentication", "-p", project_dir])
        assert result.exit_code == 0
        assert "Created spec" in result.output
        assert "DRAFT" in result.output

        specs = list_specs(project_dir)
        assert len(specs) == 1
        assert specs[0].frontmatter.status == SpecStatus.DRAFT

    def test_auto_generates_sequential_ids(self, runner: CliRunner, project_dir: str) -> None:
        runner.invoke(main, ["spec", "create", "first task", "-p", project_dir])
        runner.invoke(main, ["spec", "create", "second task", "-p", project_dir])

        specs = list_specs(project_dir)
        ids = sorted(s.frontmatter.id for s in specs)
        assert ids[0].startswith("001-")
        assert ids[1].startswith("002-")

    def test_custom_priority(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "create", "urgent task", "-p", project_dir, "--priority", "1"])
        assert result.exit_code == 0

        specs = list_specs(project_dir)
        assert specs[0].frontmatter.priority == 1

    def test_custom_complexity(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "create", "hard task", "-p", project_dir, "--complexity", "high"])
        assert result.exit_code == 0

        specs = list_specs(project_dir)
        assert specs[0].frontmatter.complexity.value == "high"

    def test_custom_plugin(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "create", "doc task", "-p", project_dir, "--plugin", "documents"])
        assert result.exit_code == 0

        specs = list_specs(project_dir)
        assert specs[0].frontmatter.plugin == "documents"


class TestSpecReady:
    def test_transitions_draft_to_ready(self, runner: CliRunner, project_dir: str) -> None:
        create_spec(project_dir, "001-test", "test task", {"status": "DRAFT"})

        result = runner.invoke(main, ["spec", "ready", "001-test", "-p", project_dir])
        assert result.exit_code == 0
        assert "READY" in result.output

        specs = list_specs(project_dir, status_filter=SpecStatus.READY)
        assert len(specs) == 1

    def test_nonexistent_spec_fails(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "ready", "999-missing", "-p", project_dir])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_non_draft_fails(self, runner: CliRunner, project_dir: str) -> None:
        create_spec(project_dir, "001-ready-already", "test", {"status": "READY"})

        result = runner.invoke(main, ["spec", "ready", "001-ready-already", "-p", project_dir])
        assert result.exit_code != 0
        assert "not DRAFT" in result.output


class TestSpecList:
    def test_lists_all_specs(self, runner: CliRunner, project_dir: str) -> None:
        create_spec(project_dir, "001-first", "task 1", {"status": "DRAFT"})
        create_spec(project_dir, "002-second", "task 2", {"status": "READY"})

        result = runner.invoke(main, ["spec", "list", "-p", project_dir])
        assert result.exit_code == 0
        assert "001-first" in result.output
        assert "002-second" in result.output

    def test_filter_by_status(self, runner: CliRunner, project_dir: str) -> None:
        create_spec(project_dir, "001-draft", "task 1", {"status": "DRAFT"})
        create_spec(project_dir, "002-ready", "task 2", {"status": "READY"})

        result = runner.invoke(main, ["spec", "list", "-p", project_dir, "-s", "READY"])
        assert result.exit_code == 0
        assert "002-ready" in result.output
        assert "001-draft" not in result.output

    def test_empty_list(self, runner: CliRunner, project_dir: str) -> None:
        result = runner.invoke(main, ["spec", "list", "-p", project_dir])
        assert result.exit_code == 0
        assert "No specs found" in result.output
