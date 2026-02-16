"""Tests for Architect agent runtime."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from tests.fixtures.stub_plugin import StubPlugin
from vizier.core.agent.context import AgentContext
from vizier.core.architect.runtime import ArchitectRuntime
from vizier.core.file_protocol.spec_io import create_spec, list_specs, read_spec
from vizier.core.models.spec import SpecStatus
from vizier.core.plugins.discovery import clear_registry, register_plugin


def _make_architect_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(role="assistant", content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=100, completion_tokens=200),
        model="test-opus",
        _hidden_params={"response_cost": 0.01},
    )


DECOMPOSITION_RESPONSE = """\
Here is the decomposition of the task:

## Sub-spec: Create data model
Complexity: low
Priority: 1
Artifacts: src/models.py

Create the User model with id, name, email fields.

@criteria/file_exists

## Sub-spec: Add API endpoint
Complexity: medium
Priority: 2
Artifacts: src/api.py, src/routes.py

Create REST API endpoint for User CRUD operations.

@criteria/file_exists
"""


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
    config_path = vizier_dir / "config.yaml"
    config_path.write_text(yaml.dump({"plugin": "test-stub", "project": "test-project"}), encoding="utf-8")
    return str(tmp_path)


@pytest.fixture()
def draft_spec(project_dir: str) -> str:
    spec = create_spec(
        project_dir,
        "001-add-auth",
        "Add authentication to the application.\n\nRequirements:\n- User registration\n- Login/logout\n- JWT tokens",
        {"status": "DRAFT", "priority": 1, "plugin": "test-stub", "complexity": "high"},
    )
    return spec.file_path or ""


class TestArchitectRuntime:
    def test_role_is_architect(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        assert runtime.role == "architect"

    def test_build_prompt_includes_spec(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "001-add-auth" in prompt
        assert "authentication" in prompt.lower()

    def test_build_prompt_includes_plugin_guide(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "file creation sub-tasks" in prompt

    def test_build_prompt_includes_criteria_library(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "@criteria/file_exists" in prompt

    def test_build_prompt_requires_spec(self) -> None:
        ctx = AgentContext(project_root="/tmp/test")
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        with pytest.raises(RuntimeError, match="requires a spec"):
            runtime.build_prompt()

    def test_build_prompt_includes_research_when_present(self, project_dir: str, draft_spec: str) -> None:
        from pathlib import Path

        spec_dir = str(Path(draft_spec).parent)
        research_path = Path(spec_dir) / "research.md"
        research_path.write_text(
            "# Prior Art Research: 001-add-auth\n\n## Summary\nFound authlib library.\n\n"
            "## Recommendation\nUSE_LIBRARY\n",
            encoding="utf-8",
        )

        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "Prior Art Research" in prompt
        assert "authlib" in prompt
        assert "USE_LIBRARY" in prompt
        assert "leverage it rather than building from scratch" in prompt

    def test_build_prompt_works_without_research(self, project_dir: str, draft_spec: str) -> None:
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "Prior Art Research" not in prompt

    def test_build_prompt_includes_constitution(self, project_dir: str, draft_spec: str) -> None:
        constitution_path = project_dir + "/.vizier/constitution.md"
        with open(constitution_path, "w", encoding="utf-8") as f:
            f.write("Always write tests first.")
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin)
        prompt = runtime.build_prompt()
        assert "Always write tests first" in prompt


class TestDecomposition:
    def test_creates_sub_specs(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)

        result = runtime.run()
        assert result == "DECOMPOSED"
        assert len(runtime.created_specs) == 2

    def test_sub_specs_have_parent_reference(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        for sub_spec in runtime.created_specs:
            loaded = read_spec(sub_spec.file_path or "")
            assert loaded.frontmatter.parent == "001-add-auth"

    def test_sub_specs_are_ready(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        for sub_spec in runtime.created_specs:
            loaded = read_spec(sub_spec.file_path or "")
            assert loaded.frontmatter.status == SpecStatus.READY

    def test_parent_marked_decomposed(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        parent = read_spec(draft_spec)
        assert parent.frontmatter.status == SpecStatus.DECOMPOSED

    def test_sub_specs_inherit_plugin(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        for sub_spec in runtime.created_specs:
            loaded = read_spec(sub_spec.file_path or "")
            assert loaded.frontmatter.plugin == "test-stub"

    def test_sub_spec_complexity_from_response(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        specs = runtime.created_specs
        assert specs[0].frontmatter.complexity == "low"
        assert specs[1].frontmatter.complexity == "medium"

    def test_sub_spec_priority_from_response(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.run()

        specs = runtime.created_specs
        assert specs[0].frontmatter.priority == 1
        assert specs[1].frontmatter.priority == 2


class TestDecomposeMethod:
    def test_decompose_returns_created_specs(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)

        created = runtime.decompose()
        assert len(created) == 2

    def test_sub_specs_listed_in_project(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response(DECOMPOSITION_RESPONSE))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        runtime.decompose()

        all_specs = list_specs(project_dir)
        ready_specs = [s for s in all_specs if s.frontmatter.status == SpecStatus.READY]
        assert len(ready_specs) == 2


class TestEmptyDecomposition:
    def test_no_sub_specs_still_decomposes(self, project_dir: str, draft_spec: str) -> None:
        mock_llm = MagicMock(return_value=_make_architect_response("No actionable sub-specs needed."))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=draft_spec)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)

        result = runtime.run()
        assert result == "DECOMPOSED"
        assert len(runtime.created_specs) == 0


class TestStuckReDecomposition:
    def test_stuck_spec_can_be_decomposed(self, project_dir: str) -> None:
        from vizier.core.file_protocol.spec_io import update_spec_status

        spec = create_spec(
            project_dir,
            "002-stuck-task",
            "Task that got stuck after many retries.",
            {"status": "READY", "plugin": "test-stub"},
        )
        spec_path = spec.file_path or ""
        update_spec_status(spec_path, SpecStatus.IN_PROGRESS)
        update_spec_status(spec_path, SpecStatus.STUCK)

        response = (
            "## Sub-spec: Simplified approach\nComplexity: low\nPriority: 1\n\nTry a simpler implementation approach.\n"
        )
        mock_llm = MagicMock(return_value=_make_architect_response(response))
        ctx = AgentContext.load_from_disk(project_dir, spec_path=spec_path)
        plugin = StubPlugin()
        runtime = ArchitectRuntime(context=ctx, plugin=plugin, llm_callable=mock_llm)
        result = runtime.run()

        assert result == "DECOMPOSED"
        parent = read_spec(spec_path)
        assert parent.frontmatter.status == SpecStatus.DECOMPOSED
        assert len(runtime.created_specs) == 1
