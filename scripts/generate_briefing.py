#!/usr/bin/env python3
"""Generate EMPIRE_BRIEFING.md for the Vizier agent workspace.

Extracts the tool registry from the MCP server, maps tools to agent roles,
and produces a structured briefing document that keeps the Vizier agent
aware of its actual capabilities.

Usage:
    PYTHONPATH=vizier-mcp python scripts/generate_briefing.py [--output PATH] [--no-haiku]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TOOL_ROLE_MAP: dict[str, list[str]] = {
    "spec_create": ["Vizier"],
    "spec_read": ["Vizier", "Pasha", "Worker", "QG"],
    "spec_list": ["Vizier", "Pasha"],
    "spec_transition": ["Pasha", "Worker", "QG"],
    "spec_update": ["Pasha"],
    "spec_write_feedback": ["QG"],
    "sentinel_check_write": ["Worker"],
    "run_command_checked": ["Worker", "QG"],
    "web_fetch_checked": ["Worker"],
    "orch_write_ping": ["Pasha", "Worker"],
    "project_get_config": ["Vizier", "Pasha", "Worker", "QG"],
    "secret_check": ["Vizier", "Pasha"],
    "system_get_logs": ["Vizier", "Pasha"],
    "system_get_errors": ["Vizier", "Pasha"],
    "system_get_status": ["Vizier"],
    "spec_analytics": ["Vizier", "Pasha"],
    "budget_record": ["Pasha", "Worker"],
    "budget_summary": ["Vizier", "Pasha"],
    "learnings_extract": ["Pasha"],
    "learnings_list": ["Vizier", "Pasha"],
    "learnings_inject": ["Pasha"],
}

TOOL_CATEGORIES: dict[str, list[str]] = {
    "Spec Lifecycle": [
        "spec_create",
        "spec_read",
        "spec_list",
        "spec_transition",
        "spec_update",
        "spec_write_feedback",
    ],
    "Sentinel Security": [
        "sentinel_check_write",
        "run_command_checked",
        "web_fetch_checked",
    ],
    "Orchestration": [
        "orch_write_ping",
        "project_get_config",
        "secret_check",
    ],
    "Observability": [
        "system_get_logs",
        "system_get_errors",
        "system_get_status",
        "spec_analytics",
    ],
    "Budget": [
        "budget_record",
        "budget_summary",
    ],
    "Learnings": [
        "learnings_extract",
        "learnings_list",
        "learnings_inject",
    ],
}

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "openclaw" / "workspaces" / "vizier" / "EMPIRE_BRIEFING.md"


def extract_tool_registry() -> list[dict[str, Any]]:
    """Extract the tool registry from the MCP server.

    Uses a temp directory for vizier_root to avoid creating directories
    at the default /data/vizier path during tool introspection.

    :return: List of tool dicts with name, description, parameters, and roles.
    """
    import asyncio
    import tempfile

    from vizier_mcp.config import ServerConfig  # type: ignore[import-not-found]
    from vizier_mcp.server import create_server  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = ServerConfig(vizier_root=Path(tmpdir))
        server = create_server(config)
        raw_tools = asyncio.run(server.list_tools())
    tools: list[dict[str, Any]] = []
    for tool in raw_tools:
        tool_info: dict[str, Any] = {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {},
            "roles": TOOL_ROLE_MAP.get(tool.name, []),
        }
        if tool.parameters:
            schema = tool.parameters.get("properties", {})
            tool_info["parameters"] = {k: v.get("type", "any") for k, v in schema.items() if k != "type"}
        tools.append(tool_info)
    return tools


def read_agent_souls() -> dict[str, str]:
    """Read all SOUL.md files from the workspaces directory.

    :return: Dict mapping agent name to SOUL.md content.
    """
    workspaces = Path(__file__).resolve().parent.parent / "openclaw" / "workspaces"
    souls: dict[str, str] = {}
    soul_dirs = {
        "vizier": "Vizier",
        "pasha-template": "Pasha",
        "worker-template": "Worker",
        "quality-gate-template": "Quality Gate",
    }
    for dirname, display_name in soul_dirs.items():
        soul_path = workspaces / dirname / "SOUL.md"
        if soul_path.exists():
            souls[display_name] = soul_path.read_text(encoding="utf-8")
    return souls


def generate_with_haiku(tools: list[dict[str, Any]], souls: dict[str, str]) -> str | None:
    """Generate briefing using Claude Haiku for natural language polish.

    :return: Markdown string on success, None on failure.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    tool_table = _build_tool_table(tools)
    agent_summaries = "\n".join(
        f"### {name}\n{content[:500]}..." if len(content) > 500 else f"### {name}\n{content}"
        for name, content in souls.items()
        if name != "Vizier"
    )

    prompt = f"""You are generating an EMPIRE_BRIEFING.md for the Vizier agent (Grand Vizier) in an Ottoman-court-metaphor work system.

The Vizier MCP server has {len(tools)} operational tools. Here is the tool registry:

{tool_table}

Here are summaries of the agent SOUL.md files:
{agent_summaries}

Generate a concise markdown briefing with these exact sections:
1. **Empire Overview** -- one paragraph summarizing the system
2. **Your Tools** -- table grouped by category showing tool name, description, which roles use it
3. **Your Agents** -- 2-3 sentences per agent (Pasha, Worker, QG) with their tool access
4. **Sentinel Security** -- 3-tier enforcement, what it protects, that it's always active
5. **Operational Commands** -- how to use system_get_status, system_get_errors, spec_analytics
6. **Implemented vs Deferred** -- v1 scope ({len(tools)} tools) vs v2 (Scout, Architect, DAG, Evidence, Plugins)

Keep it under 200 lines. Use plain ASCII only (no Unicode symbols). Be factual, not flowery."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text  # type: ignore[union-attr]
        return str(text) if text else None
    except Exception:
        return None


def _build_tool_table(tools: list[dict[str, Any]]) -> str:
    """Build a markdown table of tools grouped by category."""
    lines = ["| Category | Tool | Description | Roles |", "|----------|------|-------------|-------|"]
    for category, tool_names in TOOL_CATEGORIES.items():
        for tool_name in tool_names:
            tool = next((t for t in tools if t["name"] == tool_name), None)
            if tool:
                desc = tool["description"][:80] + "..." if len(tool["description"]) > 80 else tool["description"]
                roles = ", ".join(tool["roles"])
                lines.append(f"| {category} | `{tool_name}` | {desc} | {roles} |")
    return "\n".join(lines)


def build_structured_briefing(tools: list[dict[str, Any]], souls: dict[str, str]) -> str:
    """Build a deterministic structured briefing without LLM.

    :return: Markdown string.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    tool_count = len(tools)

    tool_table = _build_tool_table(tools)

    agent_sections: list[str] = []
    agent_tool_access: dict[str, list[str]] = {}
    for tool in tools:
        for role in tool["roles"]:
            agent_tool_access.setdefault(role, []).append(tool["name"])

    for agent_name in ["Pasha", "Worker", "Quality Gate"]:
        agent_tools = agent_tool_access.get(agent_name if agent_name != "Quality Gate" else "QG", [])
        tool_list = ", ".join(f"`{t}`" for t in agent_tools[:8])
        if agent_name == "Pasha":
            agent_sections.append(
                f"**Pasha** (per-project orchestrator, Opus): Manages spec lifecycle within a project. "
                f"Assigns Workers, handles retries, escalates blockers. Tools: {tool_list}."
            )
        elif agent_name == "Worker":
            agent_sections.append(
                f"**Worker** (spawned per-spec, Sonnet): Executes implementation work on a single spec. "
                f"All file writes and commands go through Sentinel. Tools: {tool_list}."
            )
        else:
            agent_sections.append(
                f"**Quality Gate** (spawned per-review, Sonnet): Reviews completed work against acceptance criteria. "
                f"Can run commands but cannot write files. Tools: {tool_list}."
            )

    briefing = f"""# Empire Briefing

Generated: {now}
Server version: see `system_get_status()` for live version
Tool count: {tool_count}

## Empire Overview

You are the Grand Vizier in an Ottoman-court-metaphor autonomous work system.
The Sultan (human operator) delegates work to you. You manage projects by creating
specs and routing them to Pashas. Each project has a dedicated Pasha who orchestrates
Workers and Quality Gates. All agent communication, spec management, security
enforcement, and observability flows through the Vizier MCP server -- {tool_count} tools
at your disposal.

## Your Tools

{tool_table}

## Your Agents

{chr(10).join(agent_sections)}

## Sentinel Security

Sentinel is ALWAYS active. It enforces per-project security on every command,
file write, and web fetch. Three-tier enforcement:

1. **Allowlist** -- Commands matching the project allowlist execute immediately (zero LLM cost)
2. **Denylist** -- Commands matching denylist patterns are blocked immediately (zero LLM cost)
3. **Haiku evaluator** -- Ambiguous commands are sent to Claude Haiku for safe/unsafe judgment

Workers can only write to paths in the project's `write_set` (glob patterns in `sentinel.yaml`).
Web fetches are scanned for prompt injection before content reaches agents.
Unknown agent roles are denied by default (fail-closed).

## Operational Commands

- **`system_get_status()`** -- Server health, spec counts by status, stuck/in-progress specs, active alerts
- **`system_get_status(project_id="X")`** -- Same but scoped to one project
- **`system_get_errors()`** -- Recent ERROR-level log entries
- **`spec_analytics(project_id="X")`** -- Throughput, timing, quality, sentinel stats for a project
- **`budget_summary(project_id="X")`** -- Cost breakdown by event type and spec
- **`learnings_list(project_id="X")`** -- Failure learnings from rejected/stuck specs

## Implemented vs Deferred

### v1 (Current) -- {tool_count} tools
- Spec lifecycle (6 tools): full 8-state machine, DRAFT to DONE
- Sentinel security (3 tools): write-set, command checking, web fetch scanning
- Orchestration (3 tools): ping supervisor, project config, secret check
- Observability (4 tools): structured logs, errors, system status, analytics
- Budget tracking (2 tools): cost recording and summaries
- Failure learnings (3 tools): extract, list, inject past failures

### v2 (Deferred)
- Scout agent (prior art research)
- Architect agent (task decomposition)
- DAG tools (dependency validation, topological ordering)
- Evidence system (completeness checking, verdict writing)
- Plugin framework (domain-specific tool providers)
"""
    return briefing


def main() -> None:
    """CLI entry point for briefing generation."""
    parser = argparse.ArgumentParser(description="Generate EMPIRE_BRIEFING.md")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output path")
    parser.add_argument("--no-haiku", action="store_true", help="Skip Haiku LLM generation, use template only")
    args = parser.parse_args()

    tools = extract_tool_registry()
    souls = read_agent_souls()

    print(f"Extracted {len(tools)} tools from MCP server")
    print(f"Read {len(souls)} SOUL.md files")

    missing = set(TOOL_ROLE_MAP.keys()) - {t["name"] for t in tools}
    if missing:
        print(f"WARNING: TOOL_ROLE_MAP has entries not in server: {missing}", file=sys.stderr)

    unmapped = {t["name"] for t in tools} - set(TOOL_ROLE_MAP.keys())
    if unmapped:
        print(f"WARNING: Server has tools not in TOOL_ROLE_MAP: {unmapped}", file=sys.stderr)

    briefing: str | None = None
    if not args.no_haiku:
        print("Generating briefing with Haiku...")
        briefing = generate_with_haiku(tools, souls)
        if briefing:
            print("Haiku generation successful")
        else:
            print("Haiku generation failed or unavailable, falling back to template")

    if not briefing:
        briefing = build_structured_briefing(tools, souls)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(briefing, encoding="utf-8")
    print(f"Briefing written to {args.output}")
    print(f"Briefing length: {len(briefing.splitlines())} lines")


if __name__ == "__main__":
    main()
