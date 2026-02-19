"""Tests for Pasha factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.pasha.factory import build_pasha_tools, create_pasha_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildPashaTools:
    def test_tool_count(self) -> None:
        tools = build_pasha_tools()
        assert len(tools) == 11

    def test_tool_names(self) -> None:
        tools = build_pasha_tools()
        names = {t.name for t in tools}
        expected = {
            "delegate_to_scout",
            "delegate_to_architect",
            "delegate_to_worker",
            "delegate_to_quality_gate",
            "escalate_to_ea",
            "spawn_agent",
            "report_progress",
            "read_spec",
            "update_spec_status",
            "list_specs",
            "send_message",
        }
        assert names == expected

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_pasha_tools(project_root=str(tmp_path))
        assert len(tools) == 11

    def test_tools_have_schemas(self) -> None:
        tools = build_pasha_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description


class TestCreatePashaRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Processing"))
        runtime = create_pasha_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("Delegated to Scout."))
        runtime = create_pasha_runtime(client=client)
        result = runtime.run("Process new DRAFT spec 001-auth")
        assert result.stop_reason == StopReason.COMPLETED
        assert result.final_text == "Delegated to Scout."

    def test_runtime_uses_opus(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_pasha_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_session_mode(self) -> None:
        client = make_mock_client(make_text_response("Session started"))
        runtime = create_pasha_runtime(client=client, mode="session")
        runtime.run("Let's discuss the architecture")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Session Mode" in call_kwargs["system"]

    def test_runtime_reconciliation_mode(self) -> None:
        client = make_mock_client(make_text_response("Cycle complete"))
        runtime = create_pasha_runtime(client=client, mode="reconciliation")
        runtime.run("Run reconciliation")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Reconciliation Context" in call_kwargs["system"]

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_pasha_runtime(client=client)
        assert runtime.budget.tokens_remaining == 30000

    def test_runtime_project_context(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_pasha_runtime(client=client, project_name="alpha", project_context="Uses FastAPI")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "alpha" in call_kwargs["system"]
        assert "FastAPI" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_pasha_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "delegate_to_scout" in tool_names
        assert "delegate_to_worker" in tool_names
        assert "escalate_to_ea" in tool_names
        assert "report_progress" in tool_names
