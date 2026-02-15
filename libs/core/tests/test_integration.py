"""Integration test: end-to-end flow through core infrastructure."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from vizier.core.agent.base import BaseAgent
from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.criteria import resolve_criteria_references, snapshot_criteria
from vizier.core.file_protocol.spec_io import create_spec, update_spec_status
from vizier.core.file_protocol.state_manager import StateManager
from vizier.core.logging.agent_logger import AgentLogger
from vizier.core.model_router.router import ModelRouter
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.templates import PromptTemplateRenderer
from vizier.core.sentinel.engine import SentinelEngine
from vizier.core.sentinel.policies import PolicyDecision, ToolCallRequest
from vizier.core.watcher.reconciler import Reconciler


class IntegrationWorker(BaseWorker):
    @property
    def allowed_tools(self) -> list[str]:
        return ["file_read", "file_write", "bash"]

    def get_prompt(self, spec, context) -> str:
        return f"Implement {spec.frontmatter.id}"


class IntegrationQualityGate(BaseQualityGate):
    @property
    def automated_checks(self) -> list[dict[str, str]]:
        return [{"name": "tests", "command": "uv run pytest -v"}]

    def get_prompt(self, spec, diff, context) -> str:
        return f"Validate {spec.frontmatter.id}"


class IntegrationPlugin(BasePlugin):
    @property
    def name(self) -> str:
        return "integration"

    @property
    def description(self) -> str:
        return "Integration test plugin"

    @property
    def worker_class(self) -> type[BaseWorker]:
        return IntegrationWorker

    @property
    def quality_gate_class(self) -> type[BaseQualityGate]:
        return IntegrationQualityGate

    def get_criteria_library(self) -> dict[str, str]:
        return {"tests_pass": "All tests must pass."}


class IntegrationAgent(BaseAgent):
    @property
    def role(self) -> str:
        return "worker"

    def build_prompt(self) -> str:
        if self.context.spec:
            return f"Implement {self.context.spec.frontmatter.id}"
        return "No spec"

    def process_response(self, response) -> str:
        return "REVIEW"


def _make_llm_response() -> SimpleNamespace:
    message = SimpleNamespace(content="Implementation complete")
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=500, completion_tokens=200)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.fixture
def project_root(tmp_path):
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir()
    (vizier_dir / "specs").mkdir()
    (vizier_dir / "constitution.md").write_text("Build reliable software.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("Always test edge cases.", encoding="utf-8")
    (vizier_dir / "config.yaml").write_text("plugin: integration\n", encoding="utf-8")
    return tmp_path


@pytest.mark.integration
class TestEndToEnd:
    def test_spec_lifecycle(self, project_root) -> None:
        """Test: create spec -> transition through lifecycle -> DONE."""
        spec = create_spec(project_root, "001-test-feature", "# Test Feature\n\n## Requirements\n\n- MUST work")
        assert spec.frontmatter.status == SpecStatus.DRAFT
        assert spec.file_path is not None

        spec = update_spec_status(spec.file_path, SpecStatus.READY)
        assert spec.frontmatter.status == SpecStatus.READY
        assert spec.file_path is not None

        spec = update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS, extra_updates={"assigned_to": "worker-1"})
        assert spec.frontmatter.assigned_to == "worker-1"
        assert spec.file_path is not None

        spec = update_spec_status(spec.file_path, SpecStatus.REVIEW)
        assert spec.file_path is not None
        spec = update_spec_status(spec.file_path, SpecStatus.DONE)
        assert spec.frontmatter.status == SpecStatus.DONE

    def test_criteria_snapshotting(self, project_root) -> None:
        """Test: @criteria/ references resolved and snapshotted into spec."""
        library = {"tests_pass": "All tests must pass.", "lint_clean": "Code must pass linting."}
        content = "## Acceptance Criteria\n\n- [ ] @criteria/tests_pass\n- [ ] @criteria/lint_clean\n- [ ] Custom check"
        snapshotted = snapshot_criteria(content, library)
        refs = resolve_criteria_references(content)
        assert "tests_pass" in refs
        assert "lint_clean" in refs
        assert "All tests must pass." in snapshotted
        assert "Code must pass linting." in snapshotted

    def test_state_manager_concurrent(self, project_root) -> None:
        """Test: state.json locking under concurrent access."""
        import threading

        mgr = StateManager(project_root)
        mgr.write_state(mgr.read_state().model_copy(update={"project": "test"}))

        errors: list[Exception] = []

        def increment() -> None:
            try:
                mgr.update_state(lambda s: s.model_copy(update={"current_cycle": s.current_cycle + 1}))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert mgr.read_state().current_cycle == 5

    def test_model_router_resolution(self) -> None:
        """Test: model router maps tiers with correct resolution order."""
        from vizier.core.models.config import ProjectConfig
        from vizier.core.models.spec import SpecComplexity

        project = ProjectConfig(model_tiers={"worker": "opus"})
        router = ModelRouter(project_config=project)
        assert "opus" in router.resolve("worker")
        assert "haiku" in router.resolve("worker", spec_complexity=SpecComplexity.LOW)

    def test_sentinel_pipeline(self) -> None:
        """Test: Sentinel allowlist, denylist, and fail-closed."""
        engine = SentinelEngine()
        assert engine.evaluate(ToolCallRequest(tool="read_file")).decision == PolicyDecision.ALLOW
        assert engine.evaluate(ToolCallRequest(tool="bash", command="rm -rf /")).decision == PolicyDecision.DENY
        assert engine.evaluate(ToolCallRequest(tool="bash", command="unknown_cmd")).decision == PolicyDecision.DENY

    def test_agent_fresh_context_and_logging(self, project_root, tmp_path) -> None:
        """Test: agent loads fresh context, calls LLM, logs result."""
        spec = create_spec(project_root, "001-agent-test", "# Agent Test")
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.READY)
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)

        ctx = AgentContext.load_from_disk(project_root, spec_path=spec.file_path)
        assert ctx.spec is not None

        log_path = tmp_path / "agent-log.jsonl"
        logger = AgentLogger(log_path)
        mock_llm = MagicMock(return_value=_make_llm_response())

        agent = IntegrationAgent(ctx, logger=logger, llm_callable=mock_llm)
        result = agent.run()
        assert result == "REVIEW"

        entries = logger.read_entries()
        assert len(entries) == 1
        assert entries[0].agent == "worker"
        assert entries[0].tokens_in == 500

    def test_reconciler_detects_changes(self, project_root) -> None:
        """Test: reconciler catches changes missed by watcher."""
        events = []
        reconciler = Reconciler(project_root, callback=events.append)

        create_spec(project_root, "001-test", "Test")
        result = reconciler.reconcile()
        assert len(result) == 1
        assert result[0].is_synthetic

        events.clear()
        result = reconciler.reconcile()
        assert len(result) == 0

    def test_plugin_worker_prompt(self) -> None:
        """Test: plugin worker renders prompt with spec data."""
        plugin = IntegrationPlugin()
        worker = plugin.worker_class()
        from vizier.core.models.spec import Spec, SpecFrontmatter

        spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="# Test")
        prompt = worker.get_prompt(spec, {})
        assert "001-test" in prompt

    def test_template_rendering(self) -> None:
        """Test: Jinja2 templates render with spec and context."""
        from vizier.core.models.spec import Spec, SpecFrontmatter

        renderer = PromptTemplateRenderer()
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test", plugin="integration"), content="Build the thing.")
        result = renderer.render_string("# {{ spec.id }}\n\nPlugin: {{ spec.plugin }}\n\n{{ content }}", spec)
        assert "001-test" in result
        assert "integration" in result
        assert "Build the thing." in result

    def test_worker_implicit_completion(self, project_root) -> None:
        """Test: worker clean exit transitions spec to REVIEW."""
        spec = create_spec(project_root, "001-implicit", "content")
        assert spec.file_path is not None
        update_spec_status(spec.file_path, SpecStatus.READY)
        update_spec_status(spec.file_path, SpecStatus.IN_PROGRESS)

        ctx = AgentContext.load_from_disk(project_root, spec_path=spec.file_path)
        mock_llm = MagicMock(return_value=_make_llm_response())
        agent = IntegrationAgent(ctx, llm_callable=mock_llm)
        result = agent.run()
        assert result == "REVIEW"
