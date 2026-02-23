"""Tests for the briefing generator script (Phase 12: Empire Briefing).

Tests tool extraction, role mapping, structured fallback, and Haiku generation.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
from generate_briefing import (  # type: ignore[import-not-found]
    TOOL_CATEGORIES,
    TOOL_ROLE_MAP,
    build_structured_briefing,
    extract_tool_registry,
    generate_with_haiku,
    read_agent_souls,
)


class TestToolExtraction:
    """Tests for extract_tool_registry."""

    def test_extracts_all_27_tools(self) -> None:
        tools = extract_tool_registry()
        assert len(tools) == 27

    def test_each_tool_has_required_fields(self) -> None:
        tools = extract_tool_registry()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "roles" in tool
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            assert isinstance(tool["roles"], list)

    def test_tool_names_match_server(self) -> None:
        tools = extract_tool_registry()
        names = {t["name"] for t in tools}
        expected = {
            "spec_create",
            "spec_read",
            "spec_list",
            "spec_transition",
            "spec_update",
            "spec_write_feedback",
            "sentinel_check_write",
            "run_command_checked",
            "web_fetch_checked",
            "orch_write_ping",
            "project_get_config",
            "secret_check",
            "system_get_logs",
            "system_get_errors",
            "system_get_status",
            "spec_analytics",
            "budget_record",
            "budget_summary",
            "learnings_extract",
            "learnings_list",
            "learnings_inject",
            "audit_query",
            "audit_timeline",
            "audit_stats",
            "trace_record",
            "trace_query",
            "trace_timeline",
        }
        assert names == expected

    def test_descriptions_non_empty(self) -> None:
        tools = extract_tool_registry()
        for tool in tools:
            assert len(tool["description"]) > 0, f"Tool {tool['name']} has empty description"


class TestToolRoleMap:
    """Tests for TOOL_ROLE_MAP coverage."""

    def test_covers_all_registered_tools(self) -> None:
        tools = extract_tool_registry()
        tool_names = {t["name"] for t in tools}
        map_names = set(TOOL_ROLE_MAP.keys())
        assert map_names == tool_names, (
            f"Missing from map: {tool_names - map_names}, Extra in map: {map_names - tool_names}"
        )

    def test_all_roles_are_valid(self) -> None:
        valid_roles = {"Vizier", "Pasha", "Worker", "QG"}
        for tool_name, roles in TOOL_ROLE_MAP.items():
            for role in roles:
                assert role in valid_roles, f"Tool {tool_name} has invalid role {role}"

    def test_every_tool_has_at_least_one_role(self) -> None:
        for tool_name, roles in TOOL_ROLE_MAP.items():
            assert len(roles) >= 1, f"Tool {tool_name} has no roles"

    def test_categories_cover_all_tools(self) -> None:
        categorized = set()
        for tool_list in TOOL_CATEGORIES.values():
            categorized.update(tool_list)
        assert categorized == set(TOOL_ROLE_MAP.keys())


class TestStructuredBriefing:
    """Tests for build_structured_briefing (deterministic fallback)."""

    def test_produces_valid_markdown(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        assert isinstance(briefing, str)
        assert len(briefing) > 100

    def test_contains_all_required_sections(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        assert "## Empire Overview" in briefing
        assert "## Your Tools" in briefing
        assert "## Your Agents" in briefing
        assert "## Sentinel Security" in briefing
        assert "## Operational Commands" in briefing
        assert "## Implemented vs Deferred" in briefing

    def test_tool_count_mentioned(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        assert "27" in briefing

    def test_all_tool_names_in_briefing(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        for tool in tools:
            assert tool["name"] in briefing, f"Tool {tool['name']} missing from briefing"

    def test_mentions_all_agents(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        assert "Pasha" in briefing
        assert "Worker" in briefing
        assert "Quality Gate" in briefing

    def test_sentinel_section_present(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        briefing = build_structured_briefing(tools, souls)
        assert "Allowlist" in briefing
        assert "Denylist" in briefing
        assert "Haiku" in briefing
        assert "fail-closed" in briefing


class TestHaikuGeneration:
    """Tests for generate_with_haiku (mocked)."""

    def test_returns_none_without_api_key(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        with patch.dict("os.environ", {}, clear=True):
            result = generate_with_haiku(tools, souls)
        assert result is None

    def test_returns_none_without_anthropic_package(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch.dict("sys.modules", {"anthropic": None}),
        ):
            result = generate_with_haiku(tools, souls)
        assert result is None

    def test_returns_markdown_on_success(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="# Generated Briefing\n\nTest content")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            result = generate_with_haiku(tools, souls)
        assert result is not None
        assert "Generated Briefing" in result

    def test_returns_none_on_api_error(self) -> None:
        tools = extract_tool_registry()
        souls = read_agent_souls()
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch.dict("sys.modules", {"anthropic": mock_anthropic}),
        ):
            result = generate_with_haiku(tools, souls)
        assert result is None


class TestReadAgentSouls:
    """Tests for read_agent_souls."""

    def test_reads_all_four_souls(self) -> None:
        souls = read_agent_souls()
        assert len(souls) == 4
        assert "Vizier" in souls
        assert "Pasha" in souls
        assert "Worker" in souls
        assert "Quality Gate" in souls

    def test_souls_are_non_empty(self) -> None:
        souls = read_agent_souls()
        for name, content in souls.items():
            assert len(content) > 0, f"SOUL.md for {name} is empty"
