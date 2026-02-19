"""Tests for Architect factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.architect.factory import build_architect_tools, create_architect_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildArchitectTools:
    def test_tool_count(self) -> None:
        tools = build_architect_tools()
        assert len(tools) == 9

    def test_tool_names(self) -> None:
        tools = build_architect_tools()
        names = {t.name for t in tools}
        expected = {
            "read_file",
            "glob",
            "grep",
            "request_more_research",
            "create_spec",
            "read_spec",
            "update_spec_status",
            "send_message",
            "ping_supervisor",
        }
        assert names == expected

    def test_tools_have_schemas(self) -> None:
        tools = build_architect_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_architect_tools(project_root=str(tmp_path))
        assert len(tools) == 9


class TestCreateArchitectRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Plan ready"))
        runtime = create_architect_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("Decomposition complete."))
        runtime = create_architect_runtime(client=client, spec_id="001")
        result = runtime.run("Decompose spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_runtime_uses_opus_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_with_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client, model="custom-model")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client)
        assert runtime.budget.tokens_remaining == 80000

    def test_runtime_with_learnings(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client, learnings="Avoid global state")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "global state" in call_kwargs["system"]

    def test_runtime_with_architect_guide(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client, architect_guide="Layer by concern")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Layer by concern" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "create_spec" in tool_names
        assert "request_more_research" in tool_names
        assert "ping_supervisor" in tool_names

    def test_runtime_spec_id(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client, spec_id="001-auth")
        assert runtime._spec_id == "001-auth"

    def test_runtime_agent_role(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_architect_runtime(client=client)
        assert runtime._agent_role == "architect"
