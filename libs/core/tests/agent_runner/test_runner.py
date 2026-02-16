"""Tests for agent subprocess runner."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tests.fixtures.stub_plugin import StubPlugin
from vizier.core.agent_runner.runner import AgentRunner, RunResult
from vizier.core.file_protocol.spec_io import create_spec, read_spec
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.discovery import clear_registry, register_plugin


def _make_llm_response(content: str = "Implementation complete.") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        model="test-model",
        _hidden_params={"response_cost": 0.001},
    )


@pytest.fixture(autouse=True)
def _register_stub() -> Any:
    register_plugin("test-stub", StubPlugin)
    yield
    clear_registry()


@pytest.fixture()
def project_dir(tmp_path: Any) -> str:
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    specs_dir = vizier_dir / "specs"
    specs_dir.mkdir()

    config = {"plugin": "test-stub", "project": "test-project"}
    config_path = vizier_dir / "config.yaml"
    config_path.write_text(yaml.dump(config), encoding="utf-8")

    return str(tmp_path)


@pytest.fixture()
def ready_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "001-test-task",
        "Create output.txt with 'hello world'.",
        {"status": "READY", "priority": 1, "plugin": "test-stub"},
    )
    return spec.file_path or ""


class TestAgentRunnerWorker:
    def test_run_worker_success(self, project_dir: str, ready_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_llm_response())
        runner = AgentRunner(project_root=project_dir, llm_callable=mock_llm)
        result = runner.run_worker(ready_spec, worker_id="w-001")

        assert result.agent_type == "worker"
        assert result.result == "REVIEW"
        assert result.error == ""

        spec = read_spec(ready_spec)
        assert spec.frontmatter.status == SpecStatus.REVIEW

    def test_run_worker_missing_plugin(self, project_dir: str, ready_spec: str) -> None:
        clear_registry()
        config_path = Path(project_dir) / ".vizier" / "config.yaml"
        config_path.write_text(yaml.dump({"plugin": "nonexistent"}), encoding="utf-8")

        runner = AgentRunner(project_root=project_dir)
        result = runner.run_worker(ready_spec)

        assert "not found" in result.error.lower() or "Plugin" in result.error
        register_plugin("test-stub", StubPlugin)

    def test_run_worker_no_llm_raises(self, project_dir: str, ready_spec: str) -> None:
        runner = AgentRunner(project_root=project_dir)
        result = runner.run_worker(ready_spec)

        assert result.error != ""


class TestAgentRunnerQualityGate:
    def test_run_quality_gate_pass(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "002-qg-test",
            "test task",
            {"status": "READY", "plugin": "test-stub"},
        )
        from vizier.core.file_protocol.spec_io import update_spec_status

        update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path or "", SpecStatus.REVIEW)

        mock_llm = MagicMock(return_value=_make_llm_response("All criteria PASS."))
        runner = AgentRunner(project_root=project_dir, llm_callable=mock_llm)
        result = runner.run_quality_gate(spec.file_path or "", diff="+ valid code")

        assert result.agent_type == "quality_gate"
        assert result.result == "DONE"

    def test_run_quality_gate_reject(self, project_dir: str) -> None:
        spec = create_spec(
            project_dir,
            "003-qg-reject",
            "test task",
            {"status": "READY", "plugin": "test-stub"},
        )
        from vizier.core.file_protocol.spec_io import update_spec_status

        update_spec_status(spec.file_path or "", SpecStatus.IN_PROGRESS)
        update_spec_status(spec.file_path or "", SpecStatus.REVIEW)

        runner = AgentRunner(project_root=project_dir)
        result = runner.run_quality_gate(spec.file_path or "", diff="+ print('debug')")

        assert result.result == "REJECTED"


class TestRunResult:
    def test_serialization(self) -> None:
        r = RunResult(agent_type="worker", spec_id="001", result="REVIEW")
        data = r.model_dump()
        assert data["agent_type"] == "worker"
        assert data["result"] == "REVIEW"
