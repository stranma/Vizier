"""Tests for Scout factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.scout.factory import build_scout_tools, create_scout_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildScoutTools:
    def test_tool_count(self) -> None:
        tools = build_scout_tools()
        assert len(tools) == 4

    def test_tool_names(self) -> None:
        tools = build_scout_tools()
        names = {t.name for t in tools}
        assert names == {"read_file", "bash", "update_spec_status", "send_message"}

    def test_tools_have_schemas(self) -> None:
        tools = build_scout_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_scout_tools(project_root=str(tmp_path))
        assert len(tools) == 4


class TestCreateScoutRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Research complete"))
        runtime = create_scout_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("No research needed."))
        runtime = create_scout_runtime(client=client, spec_id="001")
        result = runtime.run("Research spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_runtime_uses_sonnet_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "sonnet" in call_kwargs["model"]

    def test_runtime_with_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client, model="custom-model")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client)
        assert runtime.budget.tokens_remaining == 20000

    def test_runtime_with_plugin_guide(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client, plugin_guide="Search npm first")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "npm" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "bash" in tool_names

    def test_runtime_spec_id(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_scout_runtime(client=client, spec_id="001-auth")
        assert runtime._spec_id == "001-auth"

    def test_bash_timeout_is_short(self) -> None:
        tools = build_scout_tools()
        bash_tool = next(t for t in tools if t.name == "bash")
        assert bash_tool is not None
