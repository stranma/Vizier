"""Tests for spec lifecycle tools (CRUD + state machine)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from vizier_mcp.tools.spec import (
    spec_create,
    spec_list,
    spec_read,
    spec_transition,
    spec_update,
    spec_write_feedback,
)

if TYPE_CHECKING:
    from vizier_mcp.config import ServerConfig

PROJECT_ID = "test-project"


class TestSpecCreate:
    """Tests for spec_create."""

    def test_creates_spec_in_draft(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Add auth", "Implement authentication")
        assert "spec_id" in result
        assert result["spec_id"].startswith("001-")
        assert Path(result["path"]).exists()

    def test_creates_feedback_directory(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Add auth", "Implement authentication")
        spec_id = result["spec_id"]
        assert config.projects_dir is not None
        fb_dir = config.projects_dir / PROJECT_ID / "specs" / spec_id / "feedback"
        assert fb_dir.is_dir()

    def test_sequential_ids(self, config: ServerConfig, project_dir: Path) -> None:
        r1 = spec_create(config, PROJECT_ID, "First", "First spec")
        r2 = spec_create(config, PROJECT_ID, "Second", "Second spec")
        assert r1["spec_id"].startswith("001-")
        assert r2["spec_id"].startswith("002-")

    def test_with_artifacts_and_criteria(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(
            config,
            PROJECT_ID,
            "Add auth",
            "Implement auth",
            artifacts=["src/auth.py"],
            criteria=["Tests pass"],
        )
        data = spec_read(config, PROJECT_ID, result["spec_id"])
        assert data["artifacts"] == ["src/auth.py"]
        assert data["criteria"] == ["Tests pass"]

    def test_with_depends_on(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Add auth", "Implement auth", depends_on=["001-setup"])
        data = spec_read(config, PROJECT_ID, result["spec_id"])
        assert data["metadata"]["depends_on"] == ["001-setup"]

    def test_complexity_parameter(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Complex task", "Big work", complexity="HIGH")
        data = spec_read(config, PROJECT_ID, result["spec_id"])
        assert data["metadata"]["complexity"] == "HIGH"


class TestSpecRead:
    """Tests for spec_read."""

    def test_read_existing_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Test Spec", "The body")
        data = spec_read(config, PROJECT_ID, result["spec_id"])
        assert data["metadata"]["title"] == "Test Spec"
        assert data["metadata"]["status"] == "DRAFT"
        assert data["body"] == "The body"

    def test_read_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_read(config, PROJECT_ID, "999-nonexistent")
        assert "error" in result

    def test_read_preserves_metadata(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_create(config, PROJECT_ID, "Full Spec", "Body", complexity="HIGH")
        data = spec_read(config, PROJECT_ID, result["spec_id"])
        assert data["metadata"]["complexity"] == "HIGH"
        assert data["metadata"]["project_id"] == PROJECT_ID


class TestSpecList:
    """Tests for spec_list."""

    def test_empty_project(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_list(config, PROJECT_ID)
        assert result["specs"] == []

    def test_lists_all_specs(self, config: ServerConfig, project_dir: Path) -> None:
        spec_create(config, PROJECT_ID, "First", "First spec")
        spec_create(config, PROJECT_ID, "Second", "Second spec")
        result = spec_list(config, PROJECT_ID)
        assert len(result["specs"]) == 2

    def test_filter_by_status(self, config: ServerConfig, project_dir: Path) -> None:
        r1 = spec_create(config, PROJECT_ID, "First", "First spec")
        spec_create(config, PROJECT_ID, "Second", "Second spec")
        spec_transition(config, PROJECT_ID, r1["spec_id"], "READY", "pasha")

        draft_specs = spec_list(config, PROJECT_ID, status_filter="DRAFT")
        assert len(draft_specs["specs"]) == 1

        ready_specs = spec_list(config, PROJECT_ID, status_filter="READY")
        assert len(ready_specs["specs"]) == 1

    def test_filter_returns_empty_for_no_match(self, config: ServerConfig, project_dir: Path) -> None:
        spec_create(config, PROJECT_ID, "First", "First spec")
        result = spec_list(config, PROJECT_ID, status_filter="DONE")
        assert result["specs"] == []

    def test_nonexistent_project(self, config: ServerConfig) -> None:
        result = spec_list(config, "nonexistent-project")
        assert result["specs"] == []


class TestSpecTransition:
    """Tests for spec_transition."""

    def test_draft_to_ready(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_transition(config, PROJECT_ID, r["spec_id"], "READY", "pasha")
        assert result["success"] is True
        assert result["from_status"] == "DRAFT"
        assert result["to_status"] == "READY"

    def test_full_happy_path(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        assert spec_transition(config, PROJECT_ID, sid, "READY", "pasha")["success"]
        assert spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "worker")["success"]
        assert spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")["success"]
        assert spec_transition(config, PROJECT_ID, sid, "DONE", "quality_gate")["success"]

        data = spec_read(config, PROJECT_ID, sid)
        assert data["metadata"]["status"] == "DONE"

    def test_rejection_retry_path(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "worker")
        spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")
        spec_transition(config, PROJECT_ID, sid, "REJECTED", "quality_gate")
        result = spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        assert result["success"]

        data = spec_read(config, PROJECT_ID, sid)
        assert data["metadata"]["retry_count"] == 1

    def test_rejected_to_stuck(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "worker")
        spec_transition(config, PROJECT_ID, sid, "REVIEW", "worker")
        spec_transition(config, PROJECT_ID, sid, "REJECTED", "quality_gate")
        result = spec_transition(config, PROJECT_ID, sid, "STUCK", "pasha")
        assert result["success"]
        assert result["to_status"] == "STUCK"

    def test_invalid_transition_returns_error(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_transition(config, PROJECT_ID, r["spec_id"], "DONE", "pasha")
        assert result["success"] is False
        assert "Invalid transition" in result["error"]

    def test_invalid_status_string(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_transition(config, PROJECT_ID, r["spec_id"], "BANANAS", "pasha")
        assert result["success"] is False
        assert "Invalid status" in result["error"]

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_transition(config, PROJECT_ID, "999-nope", "READY", "pasha")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_in_progress_sets_claimed_at(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "worker")
        data = spec_read(config, PROJECT_ID, sid)
        assert data["metadata"]["claimed_at"] is not None
        assert data["metadata"]["assigned_agent"] == "worker"

    def test_interrupted_to_ready_increments_retry(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        spec_transition(config, PROJECT_ID, sid, "IN_PROGRESS", "worker")
        spec_transition(config, PROJECT_ID, sid, "INTERRUPTED", "system")
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        data = spec_read(config, PROJECT_ID, sid)
        assert data["metadata"]["retry_count"] == 1

    def test_ready_to_stuck_for_exhausted_retries(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        sid = r["spec_id"]
        spec_transition(config, PROJECT_ID, sid, "READY", "pasha")
        result = spec_transition(config, PROJECT_ID, sid, "STUCK", "pasha")
        assert result["success"]


class TestSpecUpdate:
    """Tests for spec_update."""

    def test_update_retry_count(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_update(config, PROJECT_ID, r["spec_id"], {"retry_count": 3})
        assert result["success"]
        assert "retry_count" in result["updated_fields"]
        data = spec_read(config, PROJECT_ID, r["spec_id"])
        assert data["metadata"]["retry_count"] == 3

    def test_update_assigned_agent(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_update(config, PROJECT_ID, r["spec_id"], {"assigned_agent": "worker-1"})
        assert result["success"]
        data = spec_read(config, PROJECT_ID, r["spec_id"])
        assert data["metadata"]["assigned_agent"] == "worker-1"

    def test_reject_immutable_field(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_update(config, PROJECT_ID, r["spec_id"], {"status": "DONE"})
        assert "error" in result
        assert "immutable" in result["error"].lower()

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_update(config, PROJECT_ID, "999-nope", {"retry_count": 1})
        assert "error" in result


class TestSpecWriteFeedback:
    """Tests for spec_write_feedback."""

    def test_writes_feedback_file(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_write_feedback(config, PROJECT_ID, r["spec_id"], "REJECT", "Missing unit tests")
        assert "path" in result
        path = Path(result["path"])
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["verdict"] == "REJECT"
        assert data["feedback"] == "Missing unit tests"

    def test_accept_verdict(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        result = spec_write_feedback(config, PROJECT_ID, r["spec_id"], "ACCEPT", "All criteria pass")
        path = Path(result["path"])
        assert "accept" in path.name

    def test_nonexistent_spec(self, config: ServerConfig, project_dir: Path) -> None:
        result = spec_write_feedback(config, PROJECT_ID, "999-nope", "REJECT", "Bad")
        assert "error" in result

    def test_multiple_feedback_files(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Test", "Body")
        spec_write_feedback(config, PROJECT_ID, r["spec_id"], "REJECT", "First rejection")
        spec_write_feedback(config, PROJECT_ID, r["spec_id"], "REJECT", "Second rejection")
        assert config.projects_dir is not None
        fb_dir = config.projects_dir / PROJECT_ID / "specs" / r["spec_id"] / "feedback"
        files = list(fb_dir.glob("*.json"))
        assert len(files) >= 2


class TestSpecIntegration:
    """Integration test: full spec lifecycle DRAFT -> READY -> IN_PROGRESS -> REVIEW -> DONE."""

    def test_happy_path_lifecycle(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(
            config,
            PROJECT_ID,
            "Build login page",
            "Create a login page with email/password fields",
            complexity="MEDIUM",
            artifacts=["src/login.py", "tests/test_login.py"],
            criteria=["Tests pass", "Form validates input"],
        )
        spec_id = r["spec_id"]

        data = spec_read(config, PROJECT_ID, spec_id)
        assert data["metadata"]["status"] == "DRAFT"
        assert data["artifacts"] == ["src/login.py", "tests/test_login.py"]

        assert spec_transition(config, PROJECT_ID, spec_id, "READY", "pasha")["success"]

        assert spec_transition(config, PROJECT_ID, spec_id, "IN_PROGRESS", "worker")["success"]
        data = spec_read(config, PROJECT_ID, spec_id)
        assert data["metadata"]["claimed_at"] is not None

        assert spec_transition(config, PROJECT_ID, spec_id, "REVIEW", "worker")["success"]

        spec_write_feedback(config, PROJECT_ID, spec_id, "ACCEPT", "All criteria pass")

        assert spec_transition(config, PROJECT_ID, spec_id, "DONE", "quality_gate")["success"]

        data = spec_read(config, PROJECT_ID, spec_id)
        assert data["metadata"]["status"] == "DONE"

        all_specs = spec_list(config, PROJECT_ID)
        assert len(all_specs["specs"]) == 1
        assert all_specs["specs"][0]["status"] == "DONE"

    def test_rejection_retry_lifecycle(self, config: ServerConfig, project_dir: Path) -> None:
        r = spec_create(config, PROJECT_ID, "Build feature", "Do the thing")
        spec_id = r["spec_id"]

        spec_transition(config, PROJECT_ID, spec_id, "READY", "pasha")
        spec_transition(config, PROJECT_ID, spec_id, "IN_PROGRESS", "worker")
        spec_transition(config, PROJECT_ID, spec_id, "REVIEW", "worker")

        fb_result = spec_write_feedback(config, PROJECT_ID, spec_id, "REJECT", "Tests are missing")
        assert Path(fb_result["path"]).exists()
        spec_transition(config, PROJECT_ID, spec_id, "REJECTED", "quality_gate")

        spec_transition(config, PROJECT_ID, spec_id, "READY", "pasha")
        data = spec_read(config, PROJECT_ID, spec_id)
        assert data["metadata"]["retry_count"] == 1

        spec_transition(config, PROJECT_ID, spec_id, "IN_PROGRESS", "worker")
        spec_transition(config, PROJECT_ID, spec_id, "REVIEW", "worker")
        spec_write_feedback(config, PROJECT_ID, spec_id, "ACCEPT", "All good now")
        spec_transition(config, PROJECT_ID, spec_id, "DONE", "quality_gate")

        data = spec_read(config, PROJECT_ID, spec_id)
        assert data["metadata"]["status"] == "DONE"
        assert data["metadata"]["retry_count"] == 1
