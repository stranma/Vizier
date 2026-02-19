"""Tests for AgentRuntime (D47)."""

from __future__ import annotations

from unittest.mock import MagicMock

from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.budget import BudgetConfig
from vizier.core.runtime.trace import TraceLogger
from vizier.core.runtime.types import StopReason, ToolDefinition
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, SentinelResult, ToolCallRequest

from .mock_anthropic import make_mock_client, make_text_response, make_tool_use_response


def _echo_tool(**kwargs: object) -> dict[str, object]:
    """Test tool that echoes input."""
    return {"echo": kwargs}


def _failing_tool(**kwargs: object) -> None:
    """Test tool that always raises."""
    raise RuntimeError("Tool crashed")


ECHO_TOOL = ToolDefinition(
    name="echo",
    description="Echoes input back",
    input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    handler=_echo_tool,
)


class TestSimpleCompletion:
    def test_text_response(self) -> None:
        client = make_mock_client(make_text_response("Hello, I completed the task."))
        runtime = AgentRuntime(client=client, model="test-model", system_prompt="You are a test agent.")

        result = runtime.run("Do something")

        assert result.stop_reason == StopReason.COMPLETED
        assert result.final_text == "Hello, I completed the task."
        assert result.tokens_used == 150
        assert result.turns == 1
        assert result.tool_calls == []

    def test_api_called_with_correct_params(self) -> None:
        client = make_mock_client(make_text_response("Done"))
        runtime = AgentRuntime(
            client=client,
            model="claude-sonnet-4-5-20250929",
            system_prompt="Test prompt",
        )

        runtime.run("My task", max_tokens_per_turn=2048)

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
        assert call_kwargs["max_tokens"] == 2048
        assert call_kwargs["system"] == "Test prompt"
        assert call_kwargs["messages"] == [{"role": "user", "content": "My task"}]


class TestToolUse:
    def test_single_tool_call(self) -> None:
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "hello"}),
            make_text_response("I called the echo tool."),
        )
        runtime = AgentRuntime(client=client, model="test", system_prompt="test", tools=[ECHO_TOOL])

        result = runtime.run("Echo hello")

        assert result.stop_reason == StopReason.COMPLETED
        assert result.final_text == "I called the echo tool."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "echo"
        assert result.tool_calls[0].tool_result == {"echo": {"message": "hello"}}
        assert result.tool_calls[0].sentinel_decision == "ALLOW"
        assert result.turns == 2

    def test_multiple_tool_calls(self) -> None:
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "first"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "second"}, tool_id="t2"),
            make_text_response("Both done."),
        )
        runtime = AgentRuntime(client=client, model="test", system_prompt="test", tools=[ECHO_TOOL])

        result = runtime.run("Do two things")

        assert result.stop_reason == StopReason.COMPLETED
        assert len(result.tool_calls) == 2
        assert result.turns == 3

    def test_unknown_tool(self) -> None:
        client = make_mock_client(
            make_tool_use_response("nonexistent", {"arg": "val"}),
            make_text_response("Handled the error."),
        )
        runtime = AgentRuntime(client=client, model="test", system_prompt="test")

        result = runtime.run("Call unknown tool")

        assert len(result.tool_calls) == 1
        assert "Unknown tool" in str(result.tool_calls[0].tool_result)

    def test_tool_error_handled(self) -> None:
        failing = ToolDefinition(
            name="fail",
            description="Always fails",
            input_schema={"type": "object"},
            handler=_failing_tool,
        )
        client = make_mock_client(
            make_tool_use_response("fail", {}),
            make_text_response("I handled the error."),
        )
        runtime = AgentRuntime(client=client, model="test", system_prompt="test", tools=[failing])

        result = runtime.run("Try the failing tool")

        assert len(result.tool_calls) == 1
        assert "Tool crashed" in str(result.tool_calls[0].tool_result)
        assert result.stop_reason == StopReason.COMPLETED


class TestSentinelIntegration:
    def test_sentinel_allows(self) -> None:
        sentinel = MagicMock(spec=SentinelEngine)
        sentinel.evaluate.return_value = SentinelResult(decision=PolicyDecision.ALLOW, reason="Allowed", policy="test")
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "ok"}),
            make_text_response("Done"),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            sentinel=sentinel,
            agent_role="worker",
            spec_id="001",
        )

        result = runtime.run("Test")

        assert result.tool_calls[0].sentinel_decision == "ALLOW"
        sentinel.evaluate.assert_called_once()
        call_arg = sentinel.evaluate.call_args[0][0]
        assert isinstance(call_arg, ToolCallRequest)
        assert call_arg.tool == "echo"
        assert call_arg.agent_role == "worker"
        assert call_arg.spec_id == "001"

    def test_sentinel_denies(self) -> None:
        sentinel = MagicMock(spec=SentinelEngine)
        sentinel.evaluate.return_value = SentinelResult(
            decision=PolicyDecision.DENY, reason="Not allowed", policy="denylist"
        )
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "bad"}),
            make_text_response("Blocked, moving on."),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            sentinel=sentinel,
        )

        result = runtime.run("Do bad thing")

        assert result.tool_calls[0].sentinel_decision == "DENY"
        assert "Blocked by Sentinel" in str(result.tool_calls[0].tool_result)


class TestBudgetEnforcement:
    def test_token_budget_stops_loop(self) -> None:
        client = make_mock_client(
            make_text_response("Turn 1", input_tokens=500, output_tokens=500),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            budget=BudgetConfig(max_tokens=500),
        )

        result = runtime.run("Big task")

        assert result.stop_reason == StopReason.COMPLETED
        assert result.tokens_used == 1000

    def test_budget_exhausted_before_second_call(self) -> None:
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "hi"}, input_tokens=400, output_tokens=200),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            budget=BudgetConfig(max_tokens=500),
        )

        result = runtime.run("Task")

        assert result.stop_reason == StopReason.BUDGET_EXHAUSTED
        assert result.tokens_used == 600
        assert result.turns == 1

    def test_turn_limit(self) -> None:
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "1"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "2"}, tool_id="t2"),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            budget=BudgetConfig(max_tokens=1_000_000, max_turns=2),
        )

        result = runtime.run("Task")

        assert result.stop_reason == StopReason.BUDGET_EXHAUSTED
        assert result.turns == 2


class TestTraceLogging:
    def test_trace_records_run_lifecycle(self) -> None:
        trace = TraceLogger()
        client = make_mock_client(make_text_response("Done"))
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            trace=trace,
            agent_role="worker",
            spec_id="001",
        )

        runtime.run("Test task")

        events = [e["event"] for e in trace.entries]
        assert "run_start" in events
        assert "run_complete" in events

    def test_trace_records_tool_calls(self) -> None:
        trace = TraceLogger()
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "hi"}),
            make_text_response("Done"),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            trace=trace,
        )

        runtime.run("Test")

        events = [e["event"] for e in trace.entries]
        assert "tool_call" in events

    def test_trace_records_sentinel_block(self) -> None:
        trace = TraceLogger()
        sentinel = MagicMock(spec=SentinelEngine)
        sentinel.evaluate.return_value = SentinelResult(decision=PolicyDecision.DENY, reason="Blocked", policy="test")
        client = make_mock_client(
            make_tool_use_response("echo", {}),
            make_text_response("OK"),
        )
        runtime = AgentRuntime(
            client=client,
            model="test",
            system_prompt="test",
            tools=[ECHO_TOOL],
            sentinel=sentinel,
            trace=trace,
        )

        runtime.run("Test")

        events = [e["event"] for e in trace.entries]
        assert "tool_blocked" in events


class TestApiError:
    def test_api_exception_returns_error_result(self) -> None:
        client = MagicMock()
        client.messages.create.side_effect = ConnectionError("Network error")
        runtime = AgentRuntime(client=client, model="test", system_prompt="test")

        result = runtime.run("Test")

        assert result.stop_reason == StopReason.ERROR
        assert "Network error" in result.error

    def test_api_error_traced(self) -> None:
        trace = TraceLogger()
        client = MagicMock()
        client.messages.create.side_effect = ConnectionError("Timeout")
        runtime = AgentRuntime(client=client, model="test", system_prompt="test", trace=trace)

        runtime.run("Test")

        events = [e["event"] for e in trace.entries]
        assert "api_error" in events


class TestNoTools:
    def test_no_tools_omits_tools_param(self) -> None:
        client = make_mock_client(make_text_response("Hi"))
        runtime = AgentRuntime(client=client, model="test", system_prompt="test")

        runtime.run("Hello")

        call_kwargs = client.messages.create.call_args.kwargs
        assert "tools" not in call_kwargs
