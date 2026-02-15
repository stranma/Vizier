"""Tests for AgentContext: fresh-context loading from disk."""

import pytest

from vizier.core.agent.context import AgentContext
from vizier.core.file_protocol.spec_io import create_spec


@pytest.fixture
def project_root(tmp_path):
    vizier_dir = tmp_path / ".vizier"
    vizier_dir.mkdir(parents=True)
    (vizier_dir / "specs").mkdir()
    (vizier_dir / "constitution.md").write_text("Be excellent.", encoding="utf-8")
    (vizier_dir / "learnings.md").write_text("Avoid XSS.", encoding="utf-8")
    (vizier_dir / "config.yaml").write_text("plugin: software\nmodel_tiers:\n  worker: haiku\n", encoding="utf-8")
    return tmp_path


class TestAgentContext:
    def test_load_from_disk_full(self, project_root) -> None:
        spec = create_spec(project_root, "001-test", "# Test")
        ctx = AgentContext.load_from_disk(project_root, spec_path=spec.file_path)
        assert ctx.constitution == "Be excellent."
        assert ctx.learnings == "Avoid XSS."
        assert ctx.config["plugin"] == "software"
        assert ctx.spec is not None
        assert ctx.spec.frontmatter.id == "001-test"

    def test_load_from_disk_no_spec(self, project_root) -> None:
        ctx = AgentContext.load_from_disk(project_root)
        assert ctx.spec is None
        assert ctx.constitution == "Be excellent."

    def test_load_from_disk_missing_files(self, tmp_path) -> None:
        (tmp_path / ".vizier").mkdir()
        ctx = AgentContext.load_from_disk(tmp_path)
        assert ctx.constitution == ""
        assert ctx.learnings == ""
        assert ctx.config == {}

    def test_context_is_independent(self, project_root) -> None:
        ctx1 = AgentContext.load_from_disk(project_root)
        ctx2 = AgentContext.load_from_disk(project_root)
        assert ctx1 is not ctx2
        assert ctx1.constitution == ctx2.constitution

    def test_as_dict(self, project_root) -> None:
        ctx = AgentContext.load_from_disk(project_root)
        d = ctx.as_dict()
        assert "constitution" in d
        assert "learnings" in d
        assert "config" in d
        assert "project_root" in d

    def test_properties_immutable(self, project_root) -> None:
        ctx = AgentContext.load_from_disk(project_root)
        assert isinstance(ctx.project_root, str)
        assert isinstance(ctx.constitution, str)
