"""Tests for failure learnings tools (Phase 2: Failure Learnings).

Tests learnings_extract, learnings_list, and learnings_inject tools
for extracting failure context and injecting it into retry attempts.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import yaml

from vizier_mcp.tools.learnings import (
    _categorize_feedback,
    learnings_extract,
    learnings_inject,
    learnings_list,
)

if TYPE_CHECKING:
    from pathlib import Path

    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


def _write_spec(spec_dir: Path, status: str, title: str = "Test Spec") -> None:
    """Write a minimal spec.md with the given status."""
    spec_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "spec_id": spec_dir.name,
        "project_id": PROJECT_ID,
        "title": title,
        "status": status,
        "complexity": "MEDIUM",
        "retry_count": 0,
        "created_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    content = f"---\n{yaml.dump(meta, default_flow_style=False)}---\nSpec body here.\n"
    (spec_dir / "spec.md").write_text(content)


def _write_feedback(spec_dir: Path, verdict: str, feedback: str) -> None:
    """Write a feedback file for a spec."""
    fb_dir = spec_dir / "feedback"
    fb_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    fb_file = fb_dir / f"{ts}-{verdict}.json"
    fb_file.write_text(
        json.dumps(
            {
                "spec_id": spec_dir.name,
                "verdict": verdict,
                "feedback": feedback,
                "reviewer": "quality_gate",
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    )


def _write_ping(spec_dir: Path, urgency: str, message: str) -> None:
    """Write a ping file for a spec."""
    pings_dir = spec_dir / "pings"
    pings_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
    ping_file = pings_dir / f"{ts}-{urgency}.json"
    ping_file.write_text(
        json.dumps(
            {
                "spec_id": spec_dir.name,
                "urgency": urgency,
                "message": message,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    )


class TestLearningsExtract:
    """Tests for learnings_extract tool."""

    def test_from_rejected_spec(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-auth"
        _write_spec(spec_dir, "REJECTED", title="Auth Login")
        _write_feedback(spec_dir, "REJECT", "Tests are failing for login endpoint")

        result = learnings_extract(config, PROJECT_ID)
        assert result["extracted"] == 1
        assert len(result["learnings"]) == 1
        assert result["learnings"][0]["source_spec_id"] == "001-auth"
        assert result["learnings"][0]["category"] == "test_failure"

    def test_from_stuck_spec(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "002-api"
        _write_spec(spec_dir, "STUCK", title="API Endpoint")
        _write_ping(spec_dir, "IMPOSSIBLE", "Cannot implement - spec is contradictory")

        result = learnings_extract(config, PROJECT_ID)
        assert result["extracted"] == 1
        assert result["learnings"][0]["category"] == "impossible"

    def test_skips_done_spec(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "003-done"
        _write_spec(spec_dir, "DONE")
        _write_feedback(spec_dir, "ACCEPT", "All good")

        result = learnings_extract(config, PROJECT_ID)
        assert result["extracted"] == 0

    def test_deduplicates(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "004-dup"
        _write_spec(spec_dir, "REJECTED")
        _write_feedback(spec_dir, "REJECT", "Test failures")

        result1 = learnings_extract(config, PROJECT_ID)
        assert result1["extracted"] == 1

        result2 = learnings_extract(config, PROJECT_ID)
        assert result2["extracted"] == 0

    def test_bulk_extract(self, config: ServerConfig, project_dir: Path) -> None:
        for i in range(3):
            spec_dir = project_dir / "specs" / f"00{i + 1}-bulk"
            _write_spec(spec_dir, "REJECTED")
            _write_feedback(spec_dir, "REJECT", f"Failure {i}")

        result = learnings_extract(config, PROJECT_ID)
        assert result["extracted"] == 3

    def test_empty_project(self, config: ServerConfig, project_dir: Path) -> None:
        result = learnings_extract(config, PROJECT_ID)
        assert result["extracted"] == 0
        assert result["learnings"] == []

    def test_nonexistent_project(self, config: ServerConfig) -> None:
        result = learnings_extract(config, "nonexistent")
        assert result["extracted"] == 0

    def test_specific_spec(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir_a = project_dir / "specs" / "001-a"
        _write_spec(spec_dir_a, "REJECTED")
        _write_feedback(spec_dir_a, "REJECT", "Lint errors")

        spec_dir_b = project_dir / "specs" / "002-b"
        _write_spec(spec_dir_b, "REJECTED")
        _write_feedback(spec_dir_b, "REJECT", "Type errors")

        result = learnings_extract(config, PROJECT_ID, spec_id="001-a")
        assert result["extracted"] == 1
        assert result["learnings"][0]["source_spec_id"] == "001-a"

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = learnings_extract(config, PROJECT_ID, spec_id="999-nope")
        assert "error" in result

    def test_categorize_lint_failure(self) -> None:
        assert _categorize_feedback("ruff check found lint errors") == "lint_failure"

    def test_categorize_type_error(self) -> None:
        assert _categorize_feedback("pyright reported type errors") == "type_error"

    def test_categorize_test_failure(self) -> None:
        assert _categorize_feedback("pytest failed with assertion error") == "test_failure"

    def test_categorize_fallback(self) -> None:
        assert _categorize_feedback("something vague went wrong") == "spec_ambiguity"

    def test_writes_jsonl(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "005-jsonl"
        _write_spec(spec_dir, "REJECTED")
        _write_feedback(spec_dir, "REJECT", "Test failures")

        learnings_extract(config, PROJECT_ID)
        jsonl_file = project_dir / ".vizier" / "learnings" / "learnings.jsonl"
        assert jsonl_file.exists()
        lines = [ln for ln in jsonl_file.read_text().splitlines() if ln.strip()]
        assert len(lines) == 1


class TestLearningsList:
    """Tests for learnings_list tool."""

    def test_empty(self, config: ServerConfig, project_dir: Path) -> None:
        result = learnings_list(config, PROJECT_ID)
        assert result["learnings"] == []
        assert result["total"] == 0

    def test_all_learnings(self, config: ServerConfig, project_dir: Path) -> None:
        for i in range(3):
            spec_dir = project_dir / "specs" / f"00{i + 1}-list"
            _write_spec(spec_dir, "REJECTED")
            _write_feedback(spec_dir, "REJECT", f"Failure {i}")
        learnings_extract(config, PROJECT_ID)

        result = learnings_list(config, PROJECT_ID)
        assert result["total"] == 3
        assert len(result["learnings"]) == 3

    def test_filter_by_spec_id(self, config: ServerConfig, project_dir: Path) -> None:
        for sid in ["001-a", "002-b"]:
            spec_dir = project_dir / "specs" / sid
            _write_spec(spec_dir, "REJECTED")
            _write_feedback(spec_dir, "REJECT", "Failure")
        learnings_extract(config, PROJECT_ID)

        result = learnings_list(config, PROJECT_ID, spec_id="001-a")
        assert result["total"] == 1
        assert result["learnings"][0]["source_spec_id"] == "001-a"

    def test_filter_by_category(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir_a = project_dir / "specs" / "001-lint"
        _write_spec(spec_dir_a, "REJECTED")
        _write_feedback(spec_dir_a, "REJECT", "ruff lint errors found")

        spec_dir_b = project_dir / "specs" / "002-test"
        _write_spec(spec_dir_b, "REJECTED")
        _write_feedback(spec_dir_b, "REJECT", "pytest test failures")

        learnings_extract(config, PROJECT_ID)

        result = learnings_list(config, PROJECT_ID, category="lint_failure")
        assert result["total"] == 1
        assert result["learnings"][0]["category"] == "lint_failure"

    def test_invalid_category(self, config: ServerConfig, project_dir: Path) -> None:
        result = learnings_list(config, PROJECT_ID, category="nonexistent_category")
        assert "error" in result

    def test_limit(self, config: ServerConfig, project_dir: Path) -> None:
        for i in range(5):
            spec_dir = project_dir / "specs" / f"00{i + 1}-lim"
            _write_spec(spec_dir, "REJECTED")
            _write_feedback(spec_dir, "REJECT", f"Failure {i}")
        learnings_extract(config, PROJECT_ID)

        result = learnings_list(config, PROJECT_ID, limit=2)
        assert len(result["learnings"]) == 2
        assert result["total"] == 5

    def test_sorted_newest_first(self, config: ServerConfig, project_dir: Path) -> None:
        for i in range(3):
            spec_dir = project_dir / "specs" / f"00{i + 1}-sort"
            _write_spec(spec_dir, "REJECTED")
            _write_feedback(spec_dir, "REJECT", f"Failure {i}")
        learnings_extract(config, PROJECT_ID)

        result = learnings_list(config, PROJECT_ID)
        dates = [le["created_at"] for le in result["learnings"]]
        assert dates == sorted(dates, reverse=True)


class TestLearningsInject:
    """Tests for learnings_inject tool."""

    def test_same_spec_match(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-retry"
        _write_spec(spec_dir, "REJECTED", title="Auth Login")
        _write_feedback(spec_dir, "REJECT", "Test failures in auth login")
        learnings_extract(config, PROJECT_ID)

        _write_spec(spec_dir, "READY", title="Auth Login")

        result = learnings_inject(config, PROJECT_ID, "001-retry")
        assert len(result["matches"]) == 1
        assert "same spec" in result["matches"][0]["match_reason"]

    def test_keyword_match(self, config: ServerConfig, project_dir: Path) -> None:
        source_dir = project_dir / "specs" / "001-source"
        _write_spec(source_dir, "REJECTED", title="Authentication Module")
        _write_feedback(source_dir, "REJECT", "authentication endpoint test failures")
        learnings_extract(config, PROJECT_ID)

        target_dir = project_dir / "specs" / "002-target"
        _write_spec(target_dir, "READY", title="Authentication Refactor")

        result = learnings_inject(config, PROJECT_ID, "002-target")
        assert len(result["matches"]) >= 1
        matched_reasons = [m["match_reason"] for m in result["matches"]]
        assert any("keyword" in r for r in matched_reasons)

    def test_no_matches(self, config: ServerConfig, project_dir: Path) -> None:
        target_dir = project_dir / "specs" / "001-alone"
        _write_spec(target_dir, "READY", title="Completely Unique Topic")

        result = learnings_inject(config, PROJECT_ID, "001-alone")
        assert result["matches"] == []
        assert result["context_text"] == ""

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = learnings_inject(config, PROJECT_ID, "999-nope")
        assert "error" in result

    def test_context_text_format(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-format"
        _write_spec(spec_dir, "REJECTED", title="Format Test")
        _write_feedback(spec_dir, "REJECT", "Test failures in format module")
        learnings_extract(config, PROJECT_ID)

        _write_spec(spec_dir, "READY", title="Format Test")

        result = learnings_inject(config, PROJECT_ID, "001-format")
        assert "## Failure Learnings" in result["context_text"]
        assert "test_failure" in result["context_text"]
        assert "001-format" in result["context_text"]

    def test_max_10_limit(self, config: ServerConfig, project_dir: Path) -> None:
        for i in range(15):
            spec_dir = project_dir / "specs" / f"{i:03d}-shared"
            _write_spec(spec_dir, "REJECTED", title="Shared Topic Widget")
            _write_feedback(spec_dir, "REJECT", f"Test failure in shared topic widget {i}")
        learnings_extract(config, PROJECT_ID)

        target_dir = project_dir / "specs" / "099-target"
        _write_spec(target_dir, "READY", title="Shared Topic Widget New")

        result = learnings_inject(config, PROJECT_ID, "099-target")
        assert len(result["matches"]) <= 10


class TestLearningsIntegration:
    """Integration tests for the full extract -> list -> inject cycle."""

    def test_full_cycle(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-cycle"
        _write_spec(spec_dir, "REJECTED", title="Auth Feature")
        _write_feedback(spec_dir, "REJECT", "pytest test failures in auth feature module")

        extract_result = learnings_extract(config, PROJECT_ID)
        assert extract_result["extracted"] == 1

        list_result = learnings_list(config, PROJECT_ID)
        assert list_result["total"] == 1
        assert list_result["learnings"][0]["category"] == "test_failure"

        _write_spec(spec_dir, "READY", title="Auth Feature")
        inject_result = learnings_inject(config, PROJECT_ID, "001-cycle")
        assert len(inject_result["matches"]) >= 1
        assert inject_result["context_text"] != ""

    def test_idempotent_extraction(self, config: ServerConfig, project_dir: Path) -> None:
        spec_dir = project_dir / "specs" / "001-idem"
        _write_spec(spec_dir, "REJECTED", title="Idempotent Test")
        _write_feedback(spec_dir, "REJECT", "Failure")

        r1 = learnings_extract(config, PROJECT_ID)
        assert r1["extracted"] == 1

        r2 = learnings_extract(config, PROJECT_ID)
        assert r2["extracted"] == 0

        result = learnings_list(config, PROJECT_ID)
        assert result["total"] == 1
