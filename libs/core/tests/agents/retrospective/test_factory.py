"""Tests for Retrospective factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.retrospective.factory import build_retrospective_tools, create_retrospective_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildRetrospectiveTools:
    def test_tool_count(self) -> None:
        tools = build_retrospective_tools()
        assert len(tools) == 6

    def test_tool_names(self) -> None:
        tools = build_retrospective_tools()
        names = {t.name for t in tools}
        assert names == {"read_file", "glob", "grep", "read_spec", "list_specs", "send_message"}

    def test_tools_have_schemas(self) -> None:
        tools = build_retrospective_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_retrospective_tools(project_root=str(tmp_path))
        assert len(tools) == 6


class TestCreateRetrospectiveRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Analysis complete"))
        runtime = create_retrospective_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("No issues found."))
        runtime = create_retrospective_runtime(client=client)
        result = runtime.run("Analyze recent specs")
        assert result.stop_reason == StopReason.COMPLETED

    def test_runtime_uses_opus_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client)
        assert runtime.budget.tokens_remaining == 50000

    def test_runtime_with_metrics(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client, metrics_summary="Rejection: 10%")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "10%" in call_kwargs["system"]

    def test_runtime_with_debt(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client, debt_register="- lint issue")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "lint issue" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "grep" in tool_names
        assert "list_specs" in tool_names

    def test_runtime_agent_role(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_retrospective_runtime(client=client)
        assert runtime._agent_role == "retrospective"
