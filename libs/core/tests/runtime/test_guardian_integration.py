"""Integration tests: Loop Guardian + AgentRuntime (D51 + D53)."""

from __future__ import annotations

from vizier.core.runtime.agent_runtime import AgentRuntime
from vizier.core.runtime.loop_guardian import GuardianConfig, GuardianVerdict
from vizier.core.runtime.trace import TraceLogger
from vizier.core.runtime.types import StopReason, ToolDefinition

from .mock_anthropic import make_mock_client, make_text_response, make_tool_use_response


def _echo_tool(**kwargs: object) -> dict[str, object]:
    return {"echo": kwargs}


ECHO_TOOL = ToolDefinition(
    name="echo",
    description="Echoes input",
    input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
    handler=_echo_tool,
)


class TestGuardianHaltsSpinningAgent:
    def test_identical_tool_calls_halt_agent(self) -> None:
        """Agent calls the same tool 3x in a row -> guardian halts the loop."""
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "same"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "same"}, tool_id="t2"),
            make_tool_use_response("echo", {"message": "same"}, tool_id="t3"),
        )
        runtime = AgentRuntime(
            client=client, model="test", system_prompt="test",
            tools=[ECHO_TOOL],
            guardian=GuardianConfig(max_identical_calls=3),
        )

        result = runtime.run("Repeat task")

        assert result.stop_reason == StopReason.ERROR
        assert "Loop Guardian halted" in result.error
        assert len(result.tool_calls) == 3

    def test_varied_tool_calls_continue(self) -> None:
        """Agent varies tool calls -> guardian lets it continue."""
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "a"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "b"}, tool_id="t2"),
            make_tool_use_response("echo", {"message": "c"}, tool_id="t3"),
            make_text_response("Done"),
        )
        runtime = AgentRuntime(
            client=client, model="test", system_prompt="test",
            tools=[ECHO_TOOL],
            guardian=GuardianConfig(max_identical_calls=3),
        )

        result = runtime.run("Varied task")

        assert result.stop_reason == StopReason.COMPLETED

    def test_guardian_halt_traced(self) -> None:
        """Guardian halt is recorded in the trace."""
        trace = TraceLogger()
        client = make_mock_client(
            make_tool_use_response("echo", {"message": "x"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "x"}, tool_id="t2"),
        )
        runtime = AgentRuntime(
            client=client, model="test", system_prompt="test",
            tools=[ECHO_TOOL],
            guardian=GuardianConfig(max_identical_calls=2),
            trace=trace,
        )

        runtime.run("Spin")

        events = [e["event"] for e in trace.entries]
        assert "guardian_halt" in events


class TestGuardianWithLLMCheckpoint:
    def test_llm_checkpoint_halts(self) -> None:
        """LLM checkpoint says HALT -> agent stops."""
        def always_halt(summary: str) -> GuardianVerdict:
            return GuardianVerdict.HALT

        client = make_mock_client(
            make_tool_use_response("echo", {"message": "1"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "2"}, tool_id="t2"),
        )
        runtime = AgentRuntime(
            client=client, model="test", system_prompt="test",
            tools=[ECHO_TOOL],
            guardian=GuardianConfig(checkpoint_interval=2, max_identical_calls=100),
            guardian_llm_checkpoint=always_halt,
        )

        result = runtime.run("Task")

        assert result.stop_reason == StopReason.ERROR
        assert "Loop Guardian halted" in result.error

    def test_llm_checkpoint_continues(self) -> None:
        """LLM checkpoint says CONTINUE -> agent keeps going."""
        checkpoint_calls: list[str] = []

        def track_and_continue(summary: str) -> GuardianVerdict:
            checkpoint_calls.append(summary)
            return GuardianVerdict.CONTINUE

        client = make_mock_client(
            make_tool_use_response("echo", {"message": "1"}, tool_id="t1"),
            make_tool_use_response("echo", {"message": "2"}, tool_id="t2"),
            make_text_response("Done"),
        )
        runtime = AgentRuntime(
            client=client, model="test", system_prompt="test",
            tools=[ECHO_TOOL],
            guardian=GuardianConfig(checkpoint_interval=2, max_identical_calls=100),
            guardian_llm_checkpoint=track_and_continue,
        )

        result = runtime.run("Task")

        assert result.stop_reason == StopReason.COMPLETED
        assert len(checkpoint_calls) == 1
