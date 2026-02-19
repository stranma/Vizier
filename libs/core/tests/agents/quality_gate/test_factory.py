"""Tests for Quality Gate factory: tool assembly and runtime creation."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from vizier.core.agents.quality_gate.factory import (
    _resolve_qg_model,
    build_quality_gate_tools,
    create_quality_gate_runtime,
)
from vizier.core.runtime.types import StopReason

from ...runtime.mock_anthropic import make_mock_client, make_text_response


class TestBuildQualityGateTools:
    def test_tool_count(self) -> None:
        tools = build_quality_gate_tools()
        assert len(tools) == 9

    def test_tool_names(self) -> None:
        tools = build_quality_gate_tools()
        names = {t.name for t in tools}
        expected = {
            "read_file",
            "glob",
            "grep",
            "bash",
            "run_tests",
            "update_spec_status",
            "write_feedback",
            "send_message",
            "ping_supervisor",
        }
        assert names == expected

    def test_tools_have_schemas(self) -> None:
        tools = build_quality_gate_tools()
        for tool in tools:
            assert "type" in tool.input_schema
            assert tool.description

    def test_tools_with_project_root(self, tmp_path: Path) -> None:
        tools = build_quality_gate_tools(project_root=str(tmp_path))
        assert len(tools) == 9

    def test_run_tests_tool_present(self) -> None:
        tools = build_quality_gate_tools()
        run_tests = next(t for t in tools if t.name == "run_tests")
        assert run_tests is not None
        assert "evidence" in run_tests.description.lower() or "test" in run_tests.description.lower()


class TestResolveQGModel:
    def test_low_complexity_uses_sonnet(self) -> None:
        assert "sonnet" in _resolve_qg_model("LOW")

    def test_medium_complexity_uses_sonnet(self) -> None:
        assert "sonnet" in _resolve_qg_model("MEDIUM")

    def test_high_complexity_uses_opus(self) -> None:
        assert "opus" in _resolve_qg_model("HIGH")


class TestCreateQualityGateRuntime:
    def test_creates_runtime(self) -> None:
        client = make_mock_client(make_text_response("Verdict: PASS"))
        runtime = create_quality_gate_runtime(client=client)
        assert runtime is not None

    def test_runtime_runs_successfully(self) -> None:
        client = make_mock_client(make_text_response("All criteria pass."))
        runtime = create_quality_gate_runtime(client=client, spec_id="001")
        result = runtime.run("Validate spec 001")
        assert result.stop_reason == StopReason.COMPLETED

    def test_runtime_uses_sonnet_for_medium(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client, complexity="MEDIUM")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "sonnet" in call_kwargs["model"]

    def test_runtime_uses_opus_for_high(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client, complexity="HIGH")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "opus" in call_kwargs["model"]

    def test_runtime_with_custom_model(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client, model="custom-model")
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    def test_runtime_default_budget(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client)
        assert runtime.budget.tokens_remaining == 30000

    def test_runtime_with_acceptance_criteria(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(
            client=client,
            acceptance_criteria="All tests pass\nNo lint errors",
        )
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "All tests pass" in call_kwargs["system"]

    def test_runtime_with_quality_guide(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(
            client=client,
            quality_guide="Coverage must exceed 80%",
        )
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "Coverage must exceed 80%" in call_kwargs["system"]

    def test_runtime_tools_present(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client)
        runtime.run("test")
        call_kwargs = client.messages.create.call_args.kwargs
        tool_names = {t["name"] for t in call_kwargs.get("tools", [])}
        assert "read_file" in tool_names
        assert "run_tests" in tool_names
        assert "write_feedback" in tool_names
        assert "ping_supervisor" in tool_names

    def test_runtime_spec_id(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client, spec_id="001-auth")
        assert runtime._spec_id == "001-auth"

    def test_runtime_agent_role(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client)
        assert runtime._agent_role == "quality_gate"

    def test_runtime_with_evidence_dir(self, tmp_path: Path) -> None:
        evidence = str(tmp_path / "evidence")
        client = make_mock_client(make_text_response("Done"))
        runtime = create_quality_gate_runtime(client=client, evidence_dir=evidence)
        assert runtime is not None
