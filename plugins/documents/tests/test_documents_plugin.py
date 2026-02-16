"""Integration tests for DocumentsPlugin with core runtime components."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml

from vizier.core.agent.context import AgentContext
from vizier.core.agent_runner.runner import AgentRunner
from vizier.core.architect.runtime import ArchitectRuntime
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec, update_spec_status
from vizier.core.lifecycle.retry import RetryAction
from vizier.core.lifecycle.spec_lifecycle import SpecLifecycle
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.discovery import clear_registry, register_plugin
from vizier.plugins.documents.plugin import (
    DocumentReviewer,
    DocumentsPlugin,
    DocumentWriter,
)


def _make_llm_response(content: str = "done") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="test-model",
        _hidden_params={"response_cost": 0.001},
    )


@pytest.fixture()
def project_dir(tmp_path):
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    specs_dir = vizier_dir / "specs"
    specs_dir.mkdir()
    config_path = vizier_dir / "config.yaml"
    config_path.write_text(yaml.dump({"plugin": "documents", "project": "test-docs"}), encoding="utf-8")
    (vizier_dir / "constitution.md").write_text("Produce clear and accurate documents.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("Include executive summaries.", encoding="utf-8")
    return str(tmp_path)


@pytest.fixture(autouse=True)
def _register_docs_plugin():
    register_plugin("documents", DocumentsPlugin)
    yield
    clear_registry()


class TestSubclassRelationships:
    def test_documents_plugin_is_base_plugin(self) -> None:
        assert issubclass(DocumentsPlugin, BasePlugin)

    def test_document_writer_is_base_worker(self) -> None:
        assert issubclass(DocumentWriter, BaseWorker)

    def test_document_reviewer_is_base_quality_gate(self) -> None:
        assert issubclass(DocumentReviewer, BaseQualityGate)


@pytest.mark.integration
class TestDocumentsPluginIntegration:
    def test_worker_runtime_with_document_writer(self, project_dir: str) -> None:
        """Worker claims spec, renders prompt with DocumentWriter, runs LLM, transitions to REVIEW."""
        from vizier.core.worker.runtime import WorkerRuntime

        spec = create_spec(
            project_dir,
            "001-doc-worker",
            "Write a quarterly report with executive summary and revenue analysis",
            {"status": "READY", "priority": 1, "plugin": "documents"},
        )
        spec_path = spec.file_path or ""

        mock_llm = MagicMock(return_value=_make_llm_response("Document complete."))
        worker = DocumentWriter()
        WorkerRuntime.claim_spec(spec_path, "doc-w-001")

        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        runtime = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        result = runtime.run()
        assert result == "REVIEW"

        mock_llm.assert_called_once()
        call_args = mock_llm.call_args
        prompt_sent = str(call_args)
        assert "001-doc-worker" in prompt_sent

    def test_quality_gate_runtime_with_document_reviewer(self, project_dir: str) -> None:
        """QualityGate validates document output and passes to DONE."""
        from vizier.core.quality_gate.runtime import QualityGateRuntime
        from vizier.core.worker.runtime import WorkerRuntime

        spec = create_spec(
            project_dir,
            "001-doc-gate",
            "Write a project proposal",
            {"status": "READY", "priority": 1, "plugin": "documents"},
        )
        spec_path = spec.file_path or ""
        WorkerRuntime.claim_spec(spec_path, "doc-w-001")
        update_spec_status(spec_path, SpecStatus.REVIEW)

        gate = DocumentReviewer()
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        gate_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        gate_runtime = QualityGateRuntime(
            context=ctx,
            plugin_gate=gate,
            diff="+ valid document content",
            llm_callable=gate_llm,
        )
        gate_result = gate_runtime.run_full_protocol()
        assert gate_result == "DONE"

        final = read_spec(spec_path)
        assert final.frontmatter.status == SpecStatus.DONE

    def test_full_lifecycle_draft_to_done(self, project_dir: str) -> None:
        """Full lifecycle: DRAFT -> Architect decompose -> Writer produce -> Reviewer -> DONE."""
        spec = create_spec(
            project_dir,
            "001-doc-lifecycle",
            "Produce a comprehensive annual report.",
            {"status": "DRAFT", "priority": 1, "plugin": "documents"},
        )

        arch_response = "## Sub-spec: Write executive summary\nComplexity: low\nPriority: 1\n\nWrite the summary.\n"
        arch_llm = MagicMock(return_value=_make_llm_response(arch_response))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec.file_path)
        plugin = DocumentsPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=arch_llm)
        runtime.decompose()

        parent = read_spec(spec.file_path or "")
        assert parent.frontmatter.status == SpecStatus.DECOMPOSED

        children = [s for s in list_specs(project_dir) if s.frontmatter.parent == "001-doc-lifecycle"]
        assert len(children) == 1
        child_path = children[0].file_path or ""
        assert children[0].frontmatter.status == SpecStatus.READY

        worker_llm = MagicMock(return_value=_make_llm_response("Document complete."))
        worker_runner = AgentRunner(project_root=project_dir, llm_callable=worker_llm)
        worker_result = worker_runner.run_worker(child_path, worker_id="doc-w-001")
        assert worker_result.result == "REVIEW"

        gate_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        gate_runner = AgentRunner(project_root=project_dir, llm_callable=gate_llm)
        gate_result = gate_runner.run_quality_gate(child_path, diff="+ valid document")
        assert gate_result.result == "DONE"

        final_child = read_spec(child_path)
        assert final_child.frontmatter.status == SpecStatus.DONE

    def test_rejection_and_graduated_retry(self, project_dir: str) -> None:
        """Rejection triggers graduated retry: REJECTED -> IN_PROGRESS with retry increment."""
        from vizier.core.quality_gate.runtime import QualityGateRuntime
        from vizier.core.worker.runtime import WorkerRuntime

        spec = create_spec(
            project_dir,
            "001-doc-retry",
            "Write a tricky document",
            {"status": "READY", "priority": 1, "plugin": "documents"},
        )
        spec_path = spec.file_path or ""

        mock_llm = MagicMock(return_value=_make_llm_response())
        worker = DocumentWriter()
        WorkerRuntime.claim_spec(spec_path, "doc-w-001")
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        w_runtime = WorkerRuntime(context=ctx, plugin_worker=worker, llm_callable=mock_llm)
        w_runtime.run()

        reject_llm = MagicMock(return_value=_make_llm_response("FAIL: Missing citations and empty sections."))
        gate = DocumentReviewer()
        ctx2 = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        gate_runtime = QualityGateRuntime(
            context=ctx2, plugin_gate=gate, diff="+ bad document", llm_callable=reject_llm
        )
        gate_result = gate_runtime.run_full_protocol()
        assert gate_result == "REJECTED"

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.CONTINUE

        spec_after = read_spec(spec_path)
        assert spec_after.frontmatter.status == SpecStatus.IN_PROGRESS
        assert spec_after.frontmatter.retries == 1

    def test_stuck_detection(self, project_dir: str) -> None:
        """Spec reaches max retries -> STUCK status."""
        spec = create_spec(
            project_dir,
            "001-doc-stuck",
            "Impossible document task",
            {"status": "READY", "priority": 1, "plugin": "documents"},
        )
        spec_path = spec.file_path or ""
        update_spec_status(spec_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec_path, SpecStatus.REVIEW)
        update_spec_status(spec_path, SpecStatus.REJECTED, extra_updates={"retries": 9})

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.STUCK

        final = read_spec(spec_path)
        assert final.frontmatter.status == SpecStatus.STUCK

    def test_model_bump_at_retry_3(self, project_dir: str) -> None:
        """At retry 3, graduated retry escalates to model bump."""
        spec = create_spec(
            project_dir,
            "001-doc-bump",
            "Task requiring model bump",
            {"status": "READY", "plugin": "documents"},
        )
        spec_path = spec.file_path or ""
        update_spec_status(spec_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec_path, SpecStatus.REVIEW)
        update_spec_status(spec_path, SpecStatus.REJECTED, extra_updates={"retries": 2})

        lifecycle = SpecLifecycle()
        action = lifecycle.handle_rejection(spec_path)
        assert action == RetryAction.BUMP_MODEL

    def test_agent_runner_with_documents_plugin(self, project_dir: str) -> None:
        """AgentRunner loads DocumentsPlugin and runs worker + gate."""
        spec = create_spec(
            project_dir,
            "001-doc-runner",
            "Agent runner test for documents",
            {"status": "READY", "priority": 1, "plugin": "documents"},
        )

        worker_llm = MagicMock(return_value=_make_llm_response("Document done."))
        runner = AgentRunner(project_root=project_dir, llm_callable=worker_llm)
        worker_result = runner.run_worker(spec.file_path or "", worker_id="doc-w-001")
        assert worker_result.result == "REVIEW"
        assert worker_result.agent_type == "worker"
        assert worker_result.spec_id == "001-doc-runner"

        gate_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        gate_runner = AgentRunner(project_root=project_dir, llm_callable=gate_llm)
        gate_result = gate_runner.run_quality_gate(spec.file_path or "", diff="+ valid document")
        assert gate_result.result == "DONE"
        assert gate_result.agent_type == "quality_gate"
