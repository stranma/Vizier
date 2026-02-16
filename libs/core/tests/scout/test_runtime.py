"""Tests for Scout agent runtime."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tests.fixtures.stub_plugin import StubPlugin
from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.spec_io import create_spec, read_spec
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.discovery import clear_registry, register_plugin
from vizier.core.scout.classifier import ScoutDecision
from vizier.core.scout.runtime import ScoutRuntime


def _make_scout_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=50, completion_tokens=100),
        model="test-sonnet",
        _hidden_params={"response_cost": 0.005},
    )


SCOUT_LLM_RESPONSE = """\
Here are search queries for this task:

- python authentication library JWT
- oauth2 server python package
- session management python library

SUMMARY: Looking for existing Python authentication and session management libraries.
"""


@pytest.fixture(autouse=True)
def _register_stub() -> Any:
    register_plugin("test-stub", StubPlugin)
    yield
    clear_registry()


@pytest.fixture()
def project_dir(tmp_path: Path) -> str:
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    specs_dir = vizier_dir / "specs"
    specs_dir.mkdir()
    config_path = vizier_dir / "config.yaml"
    config_path.write_text(yaml.dump({"plugin": "test-stub", "project": "test-project"}), encoding="utf-8")
    return str(tmp_path)


@pytest.fixture()
def draft_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "001-add-auth",
        "Add authentication to the application.\n\nRequirements:\n- User registration\n- Login/logout",
        {"status": "DRAFT", "priority": 1, "plugin": "test-stub", "complexity": "medium"},
    )
    return spec.file_path or ""


@pytest.fixture()
def bugfix_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "002-fix-login",
        "Fix the login timeout bug that occurs after 30 seconds.",
        {"status": "DRAFT", "priority": 1, "plugin": "test-stub", "complexity": "low"},
    )
    return spec.file_path or ""


class TestScoutRuntime:
    def test_role_is_scout(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        assert runtime.role == "scout"

    def test_build_prompt_includes_spec(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "001-add-auth" in prompt
        assert "authentication" in prompt.lower()
        assert "search queries" in prompt.lower()

    def test_build_prompt_requires_spec(self) -> None:
        ctx = AgentContext(project_root="/tmp/test")
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        with pytest.raises(RuntimeError, match="requires a spec"):
            runtime.build_prompt()


class TestScoutFlow:
    def test_skip_path_for_bugfix(self, project_dir: str, bugfix_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=bugfix_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)

        report = runtime.scout()
        assert report.decision == ScoutDecision.SKIP
        assert "No external research needed" in report.summary

        loaded = read_spec(bugfix_spec)
        assert loaded.frontmatter.status == SpecStatus.SCOUTED

    def test_skip_path_writes_research_md(self, project_dir: str, bugfix_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=bugfix_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        runtime.scout()

        spec_dir = str(Path(bugfix_spec).parent)
        research_path = Path(spec_dir) / "research.md"
        assert research_path.exists()
        content = research_path.read_text(encoding="utf-8")
        assert "No external research needed" in content

    def test_research_path_with_llm(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_scout_response(SCOUT_LLM_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)

        report = runtime.scout()
        assert report.decision == ScoutDecision.RESEARCH
        assert len(report.queries) == 3
        assert "python authentication library JWT" in report.queries

        loaded = read_spec(draft_spec)
        assert loaded.frontmatter.status == SpecStatus.SCOUTED

        mock_llm.assert_called_once()

    def test_research_path_without_llm(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin, llm_callable=None)

        report = runtime.scout()
        assert report.decision == ScoutDecision.RESEARCH
        assert "No LLM available" in report.summary

        loaded = read_spec(draft_spec)
        assert loaded.frontmatter.status == SpecStatus.SCOUTED

    def test_research_writes_report_with_queries(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_scout_response(SCOUT_LLM_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.scout()

        spec_dir = str(Path(draft_spec).parent)
        research_path = Path(spec_dir) / "research.md"
        assert research_path.exists()
        content = research_path.read_text(encoding="utf-8")
        assert "python authentication library JWT" in content

    def test_scout_requires_spec(self) -> None:
        ctx = AgentContext(project_root="/tmp/test")
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        with pytest.raises(RuntimeError, match="requires a spec"):
            runtime.scout()

    def test_report_property(self, project_dir: str, bugfix_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=bugfix_spec)
        plugin = StubPlugin()
        runtime = ScoutRuntime(context=ctx, plugin=plugin)
        assert runtime.report is None
        runtime.scout()
        assert runtime.report is not None
        assert runtime.report.spec_id == "002-fix-login"
