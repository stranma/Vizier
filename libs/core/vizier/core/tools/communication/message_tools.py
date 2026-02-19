"""Communication tools: Contract A message emission, ping, briefing, progress."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vizier.core.models.messages import Ping, PingUrgency, parse_message
from vizier.core.runtime.types import ToolDefinition

if TYPE_CHECKING:
    from collections.abc import Callable


def create_send_message_tool(project_root: str = "") -> ToolDefinition:
    """Create the send_message tool for emitting typed Contract A messages.

    Messages are validated against the Contract A schema (Pydantic models)
    and serialized as JSON to the spec directory.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for send_message.
    """

    def handler(*, spec_id: str, message_json: str) -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            data = json.loads(message_json)
        except json.JSONDecodeError as e:
            return {"error": f"Invalid message JSON: {e}"}
        if "type" not in data:
            return {"error": "Message must include 'type' field"}
        try:
            msg = parse_message(data)
        except (ValueError, KeyError) as e:
            return {"error": f"Invalid message schema: {e}"}

        msg_dir = os.path.join(project_root, ".vizier", "specs", spec_id, "messages")
        try:
            os.makedirs(msg_dir, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            msg_type = data["type"]
            filename = f"{ts}-{msg_type}.json"
            filepath = os.path.join(msg_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(msg.model_dump(mode="json"), f, indent=2, default=str)
            return {
                "message_type": msg_type,
                "spec_id": spec_id,
                "file": filename,
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write message: {e}"}

    return ToolDefinition(
        name="send_message",
        description=(
            "Send a typed Contract A message for a spec. The message is validated "
            "against the schema and written to specs/<id>/messages/ as JSON."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier"},
                "message_json": {
                    "type": "string",
                    "description": (
                        "JSON string of the message. Must include 'type' field. "
                        "Valid types: TASK_ASSIGNMENT, STATUS_UPDATE, REQUEST_CLARIFICATION, "
                        "PROPOSE_PLAN, ESCALATION, QUALITY_VERDICT, RESEARCH_REPORT, PING"
                    ),
                },
            },
            "required": ["spec_id", "message_json"],
        },
        handler=handler,
    )


def create_ping_supervisor_tool(project_root: str = "") -> ToolDefinition:
    """Create the ping_supervisor tool (D50).

    Writes a Ping message file to the spec directory. The Pasha watchdog
    detects the file within ~100ms for immediate notification.

    :param project_root: Project root for spec resolution.
    :returns: ToolDefinition for ping_supervisor.
    """

    def handler(*, spec_id: str, urgency: str, message: str) -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            urg = PingUrgency(urgency)
        except ValueError:
            valid = [u.value for u in PingUrgency]
            return {"error": f"Invalid urgency '{urgency}'. Valid: {valid}"}

        ping = Ping(spec_id=spec_id, urgency=urg, message=message)

        ping_dir = os.path.join(project_root, ".vizier", "specs", spec_id, "pings")
        try:
            os.makedirs(ping_dir, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            filename = f"{ts}-{urgency}.json"
            filepath = os.path.join(ping_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(ping.model_dump(mode="json"), f, indent=2, default=str)
            return {
                "spec_id": spec_id,
                "urgency": urgency,
                "file": filename,
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write ping: {e}"}

    return ToolDefinition(
        name="ping_supervisor",
        description=(
            "Send an immediate notification to the supervisor (D50). "
            "Urgency levels: INFO (next reconciliation), QUESTION (immediate attention), "
            "BLOCKER (immediate + EA escalation). The file is detected by Pasha's watchdog."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "spec_id": {"type": "string", "description": "Spec identifier"},
                "urgency": {
                    "type": "string",
                    "description": "Urgency level: INFO, QUESTION, or BLOCKER",
                },
                "message": {"type": "string", "description": "Notification message"},
            },
            "required": ["spec_id", "urgency", "message"],
        },
        handler=handler,
    )


def create_send_briefing_tool(
    send_callback: Callable[[str], Any] | None = None,
) -> ToolDefinition:
    """Create the send_briefing tool for EA->Sultan communication.

    :param send_callback: Optional callback to deliver the briefing (e.g. Telegram send).
        If None, the briefing is only stored locally.
    :returns: ToolDefinition for send_briefing.
    """

    def handler(*, content: str, subject: str = "") -> dict[str, Any]:
        result: dict[str, Any] = {"subject": subject, "length": len(content)}
        if send_callback is not None:
            try:
                text = f"**{subject}**\n\n{content}" if subject else content
                send_callback(text)
                result["delivered"] = True
            except Exception as e:
                result["delivered"] = False
                result["delivery_error"] = str(e)
        else:
            result["delivered"] = False
            result["delivery_error"] = "No delivery callback configured"
        return result

    return ToolDefinition(
        name="send_briefing",
        description="Send a briefing to Sultan via Telegram. Used by EA for status updates, alerts, and reports.",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Briefing content (markdown)"},
                "subject": {
                    "type": "string",
                    "description": "Optional subject line for the briefing",
                    "default": "",
                },
            },
            "required": ["content"],
        },
        handler=handler,
    )


def create_report_progress_tool(project_root: str = "") -> ToolDefinition:
    """Create the report_progress tool for Pasha status reports.

    :param project_root: Project root for report storage.
    :returns: ToolDefinition for report_progress.
    """

    def handler(*, project: str, summary: str, specs_status: str = "{}") -> dict[str, Any]:
        if not project_root:
            return {"error": "No project root configured"}
        try:
            status_data = json.loads(specs_status) if specs_status != "{}" else {}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid specs_status JSON: {e}"}

        report_dir = os.path.join(project_root, "reports", project)
        try:
            os.makedirs(report_dir, exist_ok=True)
            ts = datetime.now(UTC)
            date_str = ts.strftime("%Y-%m-%d")
            existing = [f for f in os.listdir(report_dir) if f.startswith(date_str) and f.endswith(".md")]
            cycle = len(existing) + 1
            filename = f"{date_str}-cycle-{cycle:03d}.md"
            filepath = os.path.join(report_dir, filename)

            report_content = f"# Progress Report: {project}\n\n"
            report_content += f"**Date:** {ts.isoformat()}\n\n"
            report_content += f"## Summary\n\n{summary}\n\n"
            if status_data:
                report_content += "## Specs Status\n\n"
                for sid, status in status_data.items():
                    report_content += f"- **{sid}**: {status}\n"

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(report_content)

            return {
                "project": project,
                "report_file": filename,
                "path": filepath,
            }
        except Exception as e:
            return {"error": f"Failed to write report: {e}"}

    return ToolDefinition(
        name="report_progress",
        description="Write a progress report for a project. Stored in reports/<project>/ directory.",
        input_schema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name"},
                "summary": {"type": "string", "description": "Progress summary (markdown)"},
                "specs_status": {
                    "type": "string",
                    "description": "JSON string mapping spec IDs to their current status",
                    "default": "{}",
                },
            },
            "required": ["project", "summary"],
        },
        handler=handler,
    )
