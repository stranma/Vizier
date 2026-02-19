"""Tests for communication tools: send_message, ping_supervisor, send_briefing, report_progress."""

from __future__ import annotations

import json
import os
from pathlib import Path  # noqa: TC003

from vizier.core.tools.communication.message_tools import (
    create_ping_supervisor_tool,
    create_report_progress_tool,
    create_send_briefing_tool,
    create_send_message_tool,
)


def _setup_project(tmp_path: Path) -> str:
    specs_dir = tmp_path / ".vizier" / "specs" / "001-test"
    specs_dir.mkdir(parents=True)
    return str(tmp_path)


class TestSendMessage:
    def test_send_valid_message(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_send_message_tool(root)
        msg = json.dumps(
            {
                "type": "STATUS_UPDATE",
                "spec_id": "001-test",
                "state": "IN_PROGRESS",
                "progress": "Working on it",
                "blockers": [],
                "next_step": "Continue",
                "confidence": 0.8,
                "tokens_used": 5000,
            }
        )
        result = tool.handler(spec_id="001-test", message_json=msg)
        assert "error" not in result
        assert result["message_type"] == "STATUS_UPDATE"
        assert os.path.exists(result["path"])
        with open(result["path"], encoding="utf-8") as f:
            saved = json.load(f)
        assert saved["type"] == "STATUS_UPDATE"

    def test_send_ping_message(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_send_message_tool(root)
        msg = json.dumps(
            {
                "type": "PING",
                "spec_id": "001-test",
                "urgency": "QUESTION",
                "message": "Need clarification",
            }
        )
        result = tool.handler(spec_id="001-test", message_json=msg)
        assert "error" not in result
        assert result["message_type"] == "PING"

    def test_send_invalid_json(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_send_message_tool(root)
        result = tool.handler(spec_id="001-test", message_json="{bad")
        assert "error" in result
        assert "Invalid message JSON" in result["error"]

    def test_send_missing_type(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_send_message_tool(root)
        result = tool.handler(spec_id="001-test", message_json='{"spec_id": "001"}')
        assert "error" in result
        assert "type" in result["error"].lower()

    def test_send_unknown_type(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_send_message_tool(root)
        msg = json.dumps({"type": "UNKNOWN_MESSAGE", "spec_id": "001"})
        result = tool.handler(spec_id="001-test", message_json=msg)
        assert "error" in result

    def test_send_no_project_root(self) -> None:
        tool = create_send_message_tool()
        result = tool.handler(spec_id="x", message_json='{"type": "PING"}')
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_send_message_tool()
        assert tool.name == "send_message"
        assert "spec_id" in tool.input_schema["required"]
        assert "message_json" in tool.input_schema["required"]


class TestPingSupervisor:
    def test_ping_question(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_ping_supervisor_tool(root)
        result = tool.handler(spec_id="001-test", urgency="QUESTION", message="Need help")
        assert "error" not in result
        assert result["urgency"] == "QUESTION"
        assert os.path.exists(result["path"])
        with open(result["path"], encoding="utf-8") as f:
            ping = json.load(f)
        assert ping["urgency"] == "QUESTION"
        assert ping["type"] == "PING"

    def test_ping_blocker(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_ping_supervisor_tool(root)
        result = tool.handler(spec_id="001-test", urgency="BLOCKER", message="Cannot proceed")
        assert "error" not in result
        assert result["urgency"] == "BLOCKER"

    def test_ping_info(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_ping_supervisor_tool(root)
        result = tool.handler(spec_id="001-test", urgency="INFO", message="FYI update")
        assert "error" not in result
        assert result["urgency"] == "INFO"

    def test_ping_invalid_urgency(self, tmp_path: Path) -> None:
        root = _setup_project(tmp_path)
        tool = create_ping_supervisor_tool(root)
        result = tool.handler(spec_id="001-test", urgency="CRITICAL", message="x")
        assert "error" in result
        assert "Invalid urgency" in result["error"]

    def test_ping_no_project_root(self) -> None:
        tool = create_ping_supervisor_tool()
        result = tool.handler(spec_id="x", urgency="INFO", message="x")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_ping_supervisor_tool()
        assert tool.name == "ping_supervisor"
        assert "urgency" in tool.input_schema["required"]


class TestSendBriefing:
    def test_send_with_callback(self) -> None:
        sent: list[str] = []
        tool = create_send_briefing_tool(send_callback=sent.append)
        result = tool.handler(content="All systems operational.", subject="Morning Briefing")
        assert result["delivered"] is True
        assert len(sent) == 1
        assert "Morning Briefing" in sent[0]
        assert "All systems operational" in sent[0]

    def test_send_without_callback(self) -> None:
        tool = create_send_briefing_tool()
        result = tool.handler(content="Test briefing.")
        assert result["delivered"] is False
        assert "No delivery callback" in result["delivery_error"]

    def test_send_callback_error(self) -> None:
        def failing_callback(_msg: str) -> None:
            raise ConnectionError("Telegram unavailable")

        tool = create_send_briefing_tool(send_callback=failing_callback)
        result = tool.handler(content="Test.")
        assert result["delivered"] is False
        assert "Telegram unavailable" in result["delivery_error"]

    def test_json_schema(self) -> None:
        tool = create_send_briefing_tool()
        assert tool.name == "send_briefing"
        assert "content" in tool.input_schema["required"]


class TestReportProgress:
    def test_write_report(self, tmp_path: Path) -> None:
        tool = create_report_progress_tool(str(tmp_path))
        result = tool.handler(project="alpha", summary="Completed 3 of 5 specs.")
        assert "error" not in result
        assert result["project"] == "alpha"
        assert os.path.exists(result["path"])
        with open(result["path"], encoding="utf-8") as f:
            content = f.read()
        assert "Completed 3 of 5 specs" in content

    def test_write_report_with_specs_status(self, tmp_path: Path) -> None:
        tool = create_report_progress_tool(str(tmp_path))
        status = json.dumps({"001-auth": "DONE", "002-api": "IN_PROGRESS"})
        result = tool.handler(project="alpha", summary="Good progress.", specs_status=status)
        assert "error" not in result
        with open(result["path"], encoding="utf-8") as f:
            content = f.read()
        assert "001-auth" in content
        assert "DONE" in content

    def test_write_multiple_reports(self, tmp_path: Path) -> None:
        tool = create_report_progress_tool(str(tmp_path))
        r1 = tool.handler(project="beta", summary="First report.")
        r2 = tool.handler(project="beta", summary="Second report.")
        assert r1["report_file"] != r2["report_file"]

    def test_report_no_project_root(self) -> None:
        tool = create_report_progress_tool()
        result = tool.handler(project="x", summary="x")
        assert "error" in result

    def test_report_invalid_status_json(self, tmp_path: Path) -> None:
        tool = create_report_progress_tool(str(tmp_path))
        result = tool.handler(project="x", summary="x", specs_status="{bad")
        assert "error" in result

    def test_json_schema(self) -> None:
        tool = create_report_progress_tool()
        assert tool.name == "report_progress"
        assert "project" in tool.input_schema["required"]
        assert "summary" in tool.input_schema["required"]
