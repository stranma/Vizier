"""Tests for spec CRUD tools wrapping spec_io."""

from __future__ import annotations

import json
import os
from pathlib import Path  # noqa: TC003

from vizier.core.tools.state.spec_tools import (
    create_create_spec_tool,
    create_list_specs_tool,
    create_read_spec_tool,
    create_update_spec_status_tool,
    create_write_feedback_tool,
)


def _setup_project(tmp_path: Path) -> str:
    """Create the .vizier/specs directory structure."""
    specs_dir = tmp_path / ".vizier" / "specs"
    specs_dir.mkdir(parents=True)
    return str(tmp_path)


class TestCreateSpec:
    def test_create_basic_spec(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_create_spec_tool(root)
        result = tool.handler(spec_id="001-auth", content="# Auth Feature\nImplement JWT auth.")
        assert "error" not in result
        assert result["spec_id"] == "001-auth"
        assert result["status"] == "DRAFT"
        assert os.path.exists(result["file_path"])

    def test_create_with_frontmatter(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_create_spec_tool(root)
        fm = json.dumps({"priority": 3, "complexity": "high", "plugin": "documents"})
        result = tool.handler(spec_id="002-docs", content="# Docs", frontmatter=fm)
        assert "error" not in result
        assert result["spec_id"] == "002-docs"

    def test_create_with_depends_on(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_create_spec_tool(root)
        fm = json.dumps({"depends_on": ["001-base", "002-models"]})
        result = tool.handler(spec_id="003-api", content="# API", frontmatter=fm)
        assert "error" not in result

    def test_create_invalid_frontmatter(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_create_spec_tool(root)
        result = tool.handler(spec_id="bad", content="x", frontmatter="{invalid")
        assert "error" in result
        assert "Invalid frontmatter JSON" in result["error"]

    def test_create_no_project_root(self) -> None:
        tool = create_create_spec_tool()
        result = tool.handler(spec_id="x", content="x")
        assert "error" in result
        assert "No project root" in result["error"]

    def test_json_schema(self) -> None:
        tool = create_create_spec_tool()
        assert tool.name == "create_spec"
        assert "spec_id" in tool.input_schema["properties"]
        assert "content" in tool.input_schema["properties"]
        assert "spec_id" in tool.input_schema["required"]


class TestReadSpec:
    def test_read_existing_spec(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-test", content="# Test spec content")
        tool = create_read_spec_tool(root)
        result = tool.handler(spec_path=created["file_path"])
        assert "error" not in result
        assert result["spec_id"] == "001-test"
        assert result["status"] == "DRAFT"
        assert "Test spec content" in result["content"]

    def test_read_missing_spec(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_read_spec_tool(root)
        result = tool.handler(spec_path=os.path.join(root, ".vizier", "specs", "missing", "spec.md"))
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_read_relative_path(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        create_tool.handler(spec_id="001-rel", content="# Relative")
        tool = create_read_spec_tool(root)
        result = tool.handler(spec_path=".vizier/specs/001-rel/spec.md")
        assert "error" not in result
        assert result["spec_id"] == "001-rel"

    def test_json_schema(self) -> None:
        tool = create_read_spec_tool()
        assert tool.name == "read_spec"
        assert "spec_path" in tool.input_schema["required"]


class TestUpdateSpecStatus:
    def test_valid_transition(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-update", content="# Update test")
        tool = create_update_spec_status_tool(root)
        result = tool.handler(spec_path=created["file_path"], new_status="READY")
        assert "error" not in result
        assert result["status"] == "READY"

    def test_invalid_transition(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-bad", content="# Bad transition")
        tool = create_update_spec_status_tool(root)
        result = tool.handler(spec_path=created["file_path"], new_status="DONE")
        assert "error" in result
        assert "Invalid transition" in result["error"]

    def test_invalid_status_value(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-invalid", content="# Invalid")
        tool = create_update_spec_status_tool(root)
        result = tool.handler(spec_path=created["file_path"], new_status="NONEXISTENT")
        assert "error" in result
        assert "Invalid status" in result["error"]

    def test_extra_updates(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-extras", content="# Extras")
        tool = create_update_spec_status_tool(root)
        extras = json.dumps({"assigned_to": "worker-1"})
        result = tool.handler(spec_path=created["file_path"], new_status="READY", extra_updates=extras)
        assert "error" not in result
        assert result["status"] == "READY"

    def test_full_lifecycle(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-lifecycle", content="# Lifecycle")
        tool = create_update_spec_status_tool(root)
        path = created["file_path"]
        r1 = tool.handler(spec_path=path, new_status="READY")
        assert r1["status"] == "READY"
        r2 = tool.handler(spec_path=path, new_status="IN_PROGRESS")
        assert r2["status"] == "IN_PROGRESS"
        r3 = tool.handler(spec_path=path, new_status="REVIEW")
        assert r3["status"] == "REVIEW"
        r4 = tool.handler(spec_path=path, new_status="DONE")
        assert r4["status"] == "DONE"

    def test_rejection_loop(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-reject", content="# Reject")
        tool = create_update_spec_status_tool(root)
        path = created["file_path"]
        tool.handler(spec_path=path, new_status="READY")
        tool.handler(spec_path=path, new_status="IN_PROGRESS")
        tool.handler(spec_path=path, new_status="REVIEW")
        r = tool.handler(spec_path=path, new_status="REJECTED")
        assert r["status"] == "REJECTED"
        r2 = tool.handler(spec_path=path, new_status="IN_PROGRESS")
        assert r2["status"] == "IN_PROGRESS"

    def test_json_schema(self) -> None:
        tool = create_update_spec_status_tool()
        assert tool.name == "update_spec_status"
        assert "new_status" in tool.input_schema["required"]


class TestListSpecs:
    def test_list_empty(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_list_specs_tool(root)
        result = tool.handler()
        assert result["total"] == 0
        assert result["specs"] == []

    def test_list_all(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        create_tool.handler(spec_id="001-a", content="# A")
        create_tool.handler(spec_id="002-b", content="# B")
        tool = create_list_specs_tool(root)
        result = tool.handler()
        assert result["total"] == 2

    def test_list_with_filter(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        created = create_tool.handler(spec_id="001-a", content="# A")
        create_tool.handler(spec_id="002-b", content="# B")
        update_tool = create_update_spec_status_tool(root)
        update_tool.handler(spec_path=created["file_path"], new_status="READY")
        tool = create_list_specs_tool(root)
        result = tool.handler(status_filter="READY")
        assert result["total"] == 1
        assert result["specs"][0]["spec_id"] == "001-a"

    def test_list_invalid_filter(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_list_specs_tool(root)
        result = tool.handler(status_filter="INVALID")
        assert "error" in result

    def test_list_no_project_root(self) -> None:
        tool = create_list_specs_tool()
        result = tool.handler()
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_list_specs_tool()
        assert tool.name == "list_specs"


class TestWriteFeedback:
    def test_write_feedback(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        create_tool.handler(spec_id="001-fb", content="# Feedback test")
        tool = create_write_feedback_tool(root)
        result = tool.handler(spec_id="001-fb", feedback="Tests are failing on line 42.")
        assert "error" not in result
        assert result["feedback_file"] == "feedback-001.md"
        assert os.path.exists(result["path"])

    def test_write_multiple_feedback(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        create_tool.handler(spec_id="001-multi", content="# Multi")
        tool = create_write_feedback_tool(root)
        r1 = tool.handler(spec_id="001-multi", feedback="First round.")
        r2 = tool.handler(spec_id="001-multi", feedback="Second round.", author="quality_gate")
        assert r1["feedback_file"] == "feedback-001.md"
        assert r2["feedback_file"] == "feedback-002.md"

    def test_write_feedback_with_author(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        create_tool = create_create_spec_tool(root)
        create_tool.handler(spec_id="001-auth", content="# Auth")
        tool = create_write_feedback_tool(root)
        result = tool.handler(spec_id="001-auth", feedback="Looks good.", author="pasha")
        assert "error" not in result
        with open(result["path"], encoding="utf-8") as f:
            content = f.read()
        assert "by pasha" in content

    def test_write_feedback_no_project_root(self) -> None:
        tool = create_write_feedback_tool()
        result = tool.handler(spec_id="x", feedback="x")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_write_feedback_tool()
        assert tool.name == "write_feedback"
        assert "spec_id" in tool.input_schema["required"]
        assert "feedback" in tool.input_schema["required"]
