"""Tests for Quality Gate agent runtime and Completion Protocol."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from tests.fixtures.stub_plugin import StubQualityGate
from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.spec_io import create_spec, read_spec, update_spec_status
from vizier.core.models.spec import SpecStatus
from vizier.core.quality_gate.runtime import PassResult, PCCPassOutcome, QualityGateRuntime


def _make_llm_response(content: str = "All criteria PASS. Implementation is correct.") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=20),
        model="test-model",
        _hidden_params={"response_cost": 0.002},
    )


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier" / "specs"
    vizier_dir.mkdir(parents=True)
    return str(tmp_path)


@pytest.fixture()
def review_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "001-test-task",
        "Create output.txt with 'hello world'.\n\n@criteria/file_exists",
        {"status": "READY", "priority": 1, "plugin": "test-stub"},
    )
    update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS)
    update_spec_status(spec.file_path or "", SpecStatus.REVIEW)
    return spec.file_path or ""


@pytest.fixture()
def gate_context(project_dir: str, review_spec: str) -> AgentContext:
    return AgentContext.load_from_disk(project_dir, spec_path=review_spec)


@pytest.fixture()
def stub_gate() -> StubQualityGate:
    return StubQualityGate()


class TestQualityGateRuntime:
    def test_role_is_quality_gate(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate)
        assert runtime.role == "quality_gate"

    def test_build_prompt_uses_plugin(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate, diff="+ new line")
        prompt = runtime.build_prompt()
        assert "001-test-task" in prompt
        assert "+ new line" in prompt

    def test_build_prompt_requires_spec(self, stub_gate: StubQualityGate) -> None:
        ctx = AgentContext(project_root="/tmp/test")
        runtime = QualityGateRuntime(context=ctx, plugin_gate=stub_gate)
        with pytest.raises(RuntimeError, match="requires a spec"):
            runtime.build_prompt()


class TestPass1Hygiene:
    def test_clean_diff_passes(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate, diff="+ valid code")
        outcomes = runtime.run_deterministic_passes()
        hygiene = outcomes[0]
        assert hygiene.pass_name == "hygiene"
        assert hygiene.result == PassResult.PASS

    def test_debug_print_fails(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate, diff="+ print('debug value')")
        outcomes = runtime.run_deterministic_passes()
        hygiene = outcomes[0]
        assert hygiene.result == PassResult.FAIL
        assert "print" in hygiene.details.lower()

    def test_breakpoint_fails(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate, diff="+ breakpoint()")
        outcomes = runtime.run_deterministic_passes()
        hygiene = outcomes[0]
        assert hygiene.result == PassResult.FAIL

    def test_empty_diff_passes(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate, diff="")
        outcomes = runtime.run_deterministic_passes()
        hygiene = outcomes[0]
        assert hygiene.result == PassResult.PASS


class TestPass2Mechanical:
    def test_stub_checks_pass(self, gate_context: AgentContext, stub_gate: StubQualityGate) -> None:
        runtime = QualityGateRuntime(context=gate_context, plugin_gate=stub_gate)
        outcomes = runtime.run_deterministic_passes()
        mechanical = outcomes[1]
        assert mechanical.pass_name == "mechanical"
        assert mechanical.result == PassResult.PASS


class TestFullProtocol:
    def test_all_pass_results_in_done(
        self, gate_context: AgentContext, stub_gate: StubQualityGate, review_spec: str
    ) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        runtime = QualityGateRuntime(
            context=gate_context,
            plugin_gate=stub_gate,
            diff="+ valid code",
            llm_callable=mock_llm,
        )
        result = runtime.run_full_protocol()

        assert result == "DONE"
        spec = read_spec(review_spec)
        assert spec.frontmatter.status == SpecStatus.DONE

    def test_deterministic_fail_skips_llm(
        self, gate_context: AgentContext, stub_gate: StubQualityGate, review_spec: str
    ) -> None:
        mock_llm = MagicMock()
        runtime = QualityGateRuntime(
            context=gate_context,
            plugin_gate=stub_gate,
            diff="+ print('debug')",
            llm_callable=mock_llm,
        )
        result = runtime.run_full_protocol()

        assert result == "REJECTED"
        mock_llm.assert_not_called()
        spec = read_spec(review_spec)
        assert spec.frontmatter.status == SpecStatus.REJECTED

    def test_llm_fail_results_in_rejected(self, project_dir: str, stub_gate: StubQualityGate) -> None:
        spec = create_spec(project_dir, "002-llm-fail", "test task", {"status": "READY", "plugin": "test-stub"})
        update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path or "", SpecStatus.REVIEW)

        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec.file_path)
        mock_llm = MagicMock(return_value=_make_llm_response("Tests FAIL. Missing coverage for edge case."))
        runtime = QualityGateRuntime(
            context=ctx,
            plugin_gate=stub_gate,
            diff="+ some code",
            llm_callable=mock_llm,
        )
        result = runtime.run_full_protocol()

        assert result == "REJECTED"

    def test_no_llm_skips_passes_3_5(
        self, gate_context: AgentContext, stub_gate: StubQualityGate, review_spec: str
    ) -> None:
        runtime = QualityGateRuntime(
            context=gate_context,
            plugin_gate=stub_gate,
            diff="+ valid code",
        )
        result = runtime.run_full_protocol()

        assert result == "DONE"
        outcomes = runtime.pass_outcomes
        assert any(o.pass_name == "llm_review" and o.result == PassResult.SKIP for o in outcomes)


class TestFeedbackWriting:
    def test_rejection_writes_feedback_file(
        self, gate_context: AgentContext, stub_gate: StubQualityGate, review_spec: str
    ) -> None:
        runtime = QualityGateRuntime(
            context=gate_context,
            plugin_gate=stub_gate,
            diff="+ print('debug')",
        )
        runtime.run_full_protocol()

        feedback_dir = Path(review_spec).parent / "feedback"
        assert feedback_dir.exists()
        feedback_files = list(feedback_dir.glob("*.md"))
        assert len(feedback_files) == 1

        content = feedback_files[0].read_text(encoding="utf-8")
        assert "Quality Gate Feedback" in content
        assert "[FAIL]" in content

    def test_pass_does_not_write_feedback(
        self, gate_context: AgentContext, stub_gate: StubQualityGate, review_spec: str
    ) -> None:
        runtime = QualityGateRuntime(
            context=gate_context,
            plugin_gate=stub_gate,
            diff="+ valid code",
        )
        runtime.run_full_protocol()

        feedback_dir = Path(review_spec).parent / "feedback"
        if feedback_dir.exists():
            feedback_files = list(feedback_dir.glob("*.md"))
            assert len(feedback_files) == 0


class TestPCCPassOutcome:
    def test_repr(self) -> None:
        outcome = PCCPassOutcome("hygiene", PassResult.PASS, "clean")
        assert "hygiene" in repr(outcome)
        assert "PASS" in repr(outcome)
