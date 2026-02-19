"""Tests for Loop Guardian (D51)."""

from __future__ import annotations

from vizier.core.runtime.loop_guardian import (
    GuardianConfig,
    GuardianVerdict,
    LoopGuardian,
    _format_call_summary,
    _hash_input,
)


class TestDeterministicRepeatDetection:
    def test_no_repeats_continues(self) -> None:
        guardian = LoopGuardian(GuardianConfig(max_identical_calls=3))
        v1 = guardian.record_call("bash", {"command": "ls"}, success=True)
        v2 = guardian.record_call("bash", {"command": "pwd"}, success=True)
        v3 = guardian.record_call("read_file", {"path": "foo.py"}, success=True)
        assert v1 == GuardianVerdict.CONTINUE
        assert v2 == GuardianVerdict.CONTINUE
        assert v3 == GuardianVerdict.CONTINUE

    def test_identical_calls_halts(self) -> None:
        guardian = LoopGuardian(GuardianConfig(max_identical_calls=3))
        guardian.record_call("bash", {"command": "make test"}, success=False)
        guardian.record_call("bash", {"command": "make test"}, success=False)
        verdict = guardian.record_call("bash", {"command": "make test"}, success=False)
        assert verdict == GuardianVerdict.HALT

    def test_different_inputs_no_halt(self) -> None:
        guardian = LoopGuardian(GuardianConfig(max_identical_calls=3))
        guardian.record_call("bash", {"command": "test 1"}, success=True)
        guardian.record_call("bash", {"command": "test 2"}, success=True)
        verdict = guardian.record_call("bash", {"command": "test 3"}, success=True)
        assert verdict == GuardianVerdict.CONTINUE

    def test_interleaved_calls_no_halt(self) -> None:
        guardian = LoopGuardian(GuardianConfig(max_identical_calls=3))
        guardian.record_call("bash", {"command": "test"}, success=True)
        guardian.record_call("bash", {"command": "test"}, success=True)
        guardian.record_call("read_file", {"path": "x"}, success=True)
        verdict = guardian.record_call("bash", {"command": "test"}, success=True)
        assert verdict == GuardianVerdict.CONTINUE

    def test_custom_threshold(self) -> None:
        guardian = LoopGuardian(GuardianConfig(max_identical_calls=2))
        guardian.record_call("bash", {"command": "fail"}, success=False)
        verdict = guardian.record_call("bash", {"command": "fail"}, success=False)
        assert verdict == GuardianVerdict.HALT


class TestLLMCheckpoint:
    def test_checkpoint_at_interval(self) -> None:
        calls_to_llm: list[str] = []

        def mock_checkpoint(summary: str) -> GuardianVerdict:
            calls_to_llm.append(summary)
            return GuardianVerdict.CONTINUE

        guardian = LoopGuardian(
            GuardianConfig(checkpoint_interval=3, max_identical_calls=10),
            llm_checkpoint=mock_checkpoint,
        )
        for i in range(3):
            guardian.record_call("bash", {"command": f"cmd-{i}"}, success=True)

        assert len(calls_to_llm) == 1

    def test_checkpoint_returns_halt(self) -> None:
        def halting_checkpoint(summary: str) -> GuardianVerdict:
            return GuardianVerdict.HALT

        guardian = LoopGuardian(
            GuardianConfig(checkpoint_interval=2, max_identical_calls=10),
            llm_checkpoint=halting_checkpoint,
        )
        guardian.record_call("bash", {"command": "a"}, success=True)
        verdict = guardian.record_call("bash", {"command": "b"}, success=True)
        assert verdict == GuardianVerdict.HALT

    def test_checkpoint_returns_warn(self) -> None:
        def warn_checkpoint(summary: str) -> GuardianVerdict:
            return GuardianVerdict.WARN

        guardian = LoopGuardian(
            GuardianConfig(checkpoint_interval=1, max_identical_calls=10),
            llm_checkpoint=warn_checkpoint,
        )
        verdict = guardian.record_call("bash", {"command": "x"}, success=True)
        assert verdict == GuardianVerdict.WARN

    def test_no_llm_skips_checkpoint(self) -> None:
        guardian = LoopGuardian(GuardianConfig(checkpoint_interval=1))
        for i in range(5):
            verdict = guardian.record_call("bash", {"command": f"cmd-{i}"}, success=True)
            assert verdict == GuardianVerdict.CONTINUE

    def test_checkpoint_error_continues(self) -> None:
        def failing_checkpoint(summary: str) -> GuardianVerdict:
            raise RuntimeError("LLM unavailable")

        guardian = LoopGuardian(
            GuardianConfig(checkpoint_interval=1, max_identical_calls=10),
            llm_checkpoint=failing_checkpoint,
        )
        verdict = guardian.record_call("bash", {"command": "x"}, success=True)
        assert verdict == GuardianVerdict.CONTINUE

    def test_string_verdict_converted(self) -> None:
        def string_checkpoint(summary: str) -> str:
            return "WARN"

        guardian = LoopGuardian(
            GuardianConfig(checkpoint_interval=1, max_identical_calls=10),
            llm_checkpoint=string_checkpoint,
        )
        verdict = guardian.record_call("bash", {"command": "x"}, success=True)
        assert verdict == GuardianVerdict.WARN


class TestDisabledGuardian:
    def test_disabled_always_continues(self) -> None:
        guardian = LoopGuardian(GuardianConfig(enabled=False, max_identical_calls=1))
        verdict = guardian.record_call("bash", {"command": "same"}, success=False)
        assert verdict == GuardianVerdict.CONTINUE
        assert guardian.total_calls == 0


class TestGuardianState:
    def test_total_calls_tracked(self) -> None:
        guardian = LoopGuardian()
        assert guardian.total_calls == 0
        guardian.record_call("bash", {"command": "a"}, success=True)
        guardian.record_call("bash", {"command": "b"}, success=True)
        assert guardian.total_calls == 2

    def test_reset(self) -> None:
        guardian = LoopGuardian()
        guardian.record_call("bash", {"command": "a"}, success=True)
        guardian.reset()
        assert guardian.total_calls == 0
        assert guardian.call_history == []

    def test_call_history_returns_copy(self) -> None:
        guardian = LoopGuardian()
        guardian.record_call("bash", {"command": "a"}, success=True)
        history = guardian.call_history
        history.clear()
        assert len(guardian.call_history) == 1


class TestHelpers:
    def test_hash_deterministic(self) -> None:
        h1 = _hash_input("bash", {"command": "ls", "cwd": "/tmp"})
        h2 = _hash_input("bash", {"cwd": "/tmp", "command": "ls"})
        assert h1 == h2

    def test_hash_different_tools(self) -> None:
        h1 = _hash_input("bash", {"command": "ls"})
        h2 = _hash_input("read_file", {"command": "ls"})
        assert h1 != h2

    def test_format_call_summary(self) -> None:
        from vizier.core.runtime.loop_guardian import ToolCallSummary

        calls = [
            ToolCallSummary(tool_name="bash", tool_input_hash="h1", success=True, result_preview="files"),
            ToolCallSummary(tool_name="bash", tool_input_hash="h2", success=False, result_preview="error"),
        ]
        summary = _format_call_summary(calls)
        assert "1. bash [OK]" in summary
        assert "2. bash [FAIL]" in summary
