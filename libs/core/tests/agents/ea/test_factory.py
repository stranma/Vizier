"""Tests for EA factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.ea.capability_summary import build_capability
from vizier.core.agents.ea.factory import build_ea_tools, create_ea_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildEATools:
    def test_tool_count(self) -> None:
        tools = build_ea_tools()
        assert len(tools) == 6

    def test_tool_names(self) -> None:
        tools = build_ea_tools()
        names = {t.name for t in tools}
        assert names == {"read_file", "create_spec", "read_spec", "list_specs", "send_message", "send_briefing"}

    def test_tools_have_schemas(self) -> None:
        tools = build_ea_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_ea_tools(project_root=str(tmp_path))
        assert len(tools) == 6

    def test_tools_with_send_callback(self) -> None:
        sent: list[str] = []
        tools = build_ea_tools(send_callback=sent.append)
        briefing_tool = next(t for t in tools if t.name == "send_briefing")
        result = briefing_tool.handler(content="Test briefing")
        assert result["delivered"] is True
        assert len(sent) == 1


class TestCreateEARuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Hello"))
        runtime = create_ea_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("Task processed."))
        runtime = create_ea_runtime(client=client, initial_message="Build auth")
        result = runtime.run("Build auth for project-alpha")
        assert result.stop_reason == StopReason.COMPLETED
        assert result.final_text == "Task processed."

    def test_runtime_uses_opus_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_ea_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_with_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_ea_runtime(client=client, model="custom-model")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    def test_runtime_includes_capabilities_in_prompt(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        caps = [build_capability(name="alpha", plugin="software")]
        runtime = create_ea_runtime(client=client, capabilities=caps, initial_message="Build it")
        runtime.run("Build it")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "alpha" in call_kwargs["system"]
        assert "pytest" in call_kwargs["system"]

    def test_runtime_includes_priorities(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_ea_runtime(client=client, priorities="1. Ship auth", initial_message="/status")
        runtime.run("/status")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Ship auth" in call_kwargs["system"]

    def test_runtime_jit_prompt_assembly(self) -> None:
        client = make_mock_client(make_text_response("Status report"))
        runtime = create_ea_runtime(client=client, initial_message="/status")
        runtime.run("/status")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Status Report Context" in call_kwargs["system"]

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_ea_runtime(client=client)
        assert runtime.budget.tokens_remaining == 50000

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_ea_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "create_spec" in tool_names
        assert "send_briefing" in tool_names
