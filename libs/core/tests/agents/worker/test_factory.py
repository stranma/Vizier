"""Tests for Worker factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.worker.factory import _resolve_model, build_worker_tools, create_worker_runtime
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildWorkerTools:
    def test_tool_count(self) -> None:
        tools = build_worker_tools()
        assert len(tools) == 13

    def test_tool_names(self) -> None:
        tools = build_worker_tools()
        names = {t.name for t in tools}
        expected = {
            "read_file",
            "write_file",
            "edit_file",
            "bash",
            "glob",
            "grep",
            "git",
            "run_tests",
            "escalate_to_pasha",
            "update_spec_status",
            "write_feedback",
            "send_message",
            "ping_supervisor",
        }
        assert names == expected

    def test_tools_have_schemas(self) -> None:
        tools = build_worker_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_worker_tools(project_root=str(tmp_path))
        assert len(tools) == 13

    def test_write_file_enforces_write_set(self, tmp_path: Path) -> None:
        from vizier.core.tools.domain import WriteSetChecker

        checker = WriteSetChecker(["src/**/*.py"], str(tmp_path))
        tools = build_worker_tools(project_root=str(tmp_path), write_set=checker)
        write_tool = next(t for t in tools if t.name == "write_file")
        result = write_tool.handler(path="docs/readme.md", content="hello")
        assert "error" in result
        assert "denied" in result["error"].lower()


class TestResolveModel:
    def test_medium_complexity_first_try(self) -> None:
        assert "sonnet" in _resolve_model("MEDIUM", 0)

    def test_low_complexity_first_try(self) -> None:
        assert "sonnet" in _resolve_model("LOW", 0)

    def test_high_complexity_uses_opus(self) -> None:
        assert "opus" in _resolve_model("HIGH", 0)

    def test_retry_3_uses_opus(self) -> None:
        assert "opus" in _resolve_model("MEDIUM", 3)

    def test_retry_5_uses_opus(self) -> None:
        assert "opus" in _resolve_model("LOW", 5)

    def test_retry_2_stays_sonnet(self) -> None:
        assert "sonnet" in _resolve_model("MEDIUM", 2)


class TestCreateWorkerRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Work done"))
        runtime = create_worker_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("Implementation complete."))
        runtime = create_worker_runtime(client=client, spec_id="001", goal="Add auth")
        result = runtime.run("Execute spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_runtime_uses_sonnet_by_default(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "sonnet" in call_kwargs["model"]

    def test_runtime_uses_opus_for_high_complexity(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client, complexity="HIGH")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_uses_opus_on_retry(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client, retry_count=3)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_with_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client, model="custom-model")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client)
        assert runtime.budget.tokens_remaining == 100000

    def test_runtime_includes_spec_in_prompt(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(
            client=client,
            goal="Add JWT auth",
            constraints="Use PyJWT",
        )
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "JWT auth" in call_kwargs["system"]
        assert "PyJWT" in call_kwargs["system"]

    def test_runtime_includes_write_set_in_prompt(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(
            client=client,
            goal="Add feature",
            write_set_patterns=["src/**/*.py", "tests/**/*.py"],
        )
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "src/**/*.py" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "run_tests" in tool_names
        assert "ping_supervisor" in tool_names

    def test_runtime_spec_id(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client, spec_id="001-auth")
        assert runtime._spec_id == "001-auth"

    def test_runtime_agent_role(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client)
        assert runtime._agent_role == "worker"

    def test_unrestricted_write_set_in_prompt(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_worker_runtime(client=client, goal="Add feature")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "(unrestricted)" in call_kwargs["system"]
