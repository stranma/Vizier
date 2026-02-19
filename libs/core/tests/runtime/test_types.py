"""Tests for runtime type definitions."""

from vizier.core.runtime.types import RunResult, StopReason, ToolCallRecord, ToolDefinition


class TestStopReason:
    def test_values(self) -> None:
        assert StopReason.COMPLETED == "completed"
        assert StopReason.BUDGET_EXHAUSTED == "budget_exhausted"
        assert StopReason.MAX_TURNS_REACHED == "max_turns_reached"
        assert StopReason.ERROR == "error"


class TestToolDefinition:
    def test_create(self) -> None:
        def handler(**kwargs: object) -> str:
            return "ok"

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=handler,
        )
        assert tool.name == "test_tool"
        assert tool.description == "A test tool"
        assert tool.handler(x="hello") == "ok"


class TestToolCallRecord:
    def test_defaults(self) -> None:
        record = ToolCallRecord(
            tool_name="bash",
            tool_input={"command": "ls"},
            tool_result={"stdout": "file.py"},
        )
        assert record.sentinel_decision == "ALLOW"
        assert record.duration_ms == 0
        assert record.timestamp is not None


class TestRunResult:
    def test_completed(self) -> None:
        result = RunResult(stop_reason=StopReason.COMPLETED, final_text="Done")
        assert result.stop_reason == StopReason.COMPLETED
        assert result.final_text == "Done"
        assert result.tool_calls == []
        assert result.tokens_used == 0
        assert result.turns == 0
        assert result.error == ""

    def test_error(self) -> None:
        result = RunResult(stop_reason=StopReason.ERROR, error="API timeout")
        assert result.stop_reason == StopReason.ERROR
        assert result.error == "API timeout"
