"""Tests for Jinja2 prompt template rendering."""

from vizier.core.models.spec import Spec, SpecFrontmatter
from vizier.core.plugins.templates import PromptTemplateRenderer


class TestPromptTemplateRenderer:
    def test_render_string_basic(self) -> None:
        renderer = PromptTemplateRenderer()
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test", plugin="software"), content="Do the thing.")
        template = "Implement {{ spec.id }} for {{ spec.plugin }}\n\n{{ content }}"
        result = renderer.render_string(template, spec)
        assert "001-test" in result
        assert "software" in result
        assert "Do the thing." in result

    def test_render_with_context(self) -> None:
        renderer = PromptTemplateRenderer()
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="")
        template = "Learnings: {{ context.learnings }}"
        result = renderer.render_string(template, spec, context={"learnings": "Avoid XSS."})
        assert "Avoid XSS." in result

    def test_render_spec_vars(self) -> None:
        renderer = PromptTemplateRenderer()
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test", complexity="high"), content="")  # type: ignore[arg-type]
        template = "Complexity: {{ spec_complexity }}, ID: {{ spec_id }}"
        result = renderer.render_string(template, spec)
        assert "high" in result
        assert "001-test" in result

    def test_render_file(self, tmp_path) -> None:
        template_dir = tmp_path / "prompts"
        template_dir.mkdir()
        (template_dir / "worker.md").write_text("# {{ spec.id }}\n\n{{ content }}", encoding="utf-8")

        renderer = PromptTemplateRenderer(template_dir)
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="Build it.")
        result = renderer.render_file("worker.md", spec)
        assert "# 001-test" in result
        assert "Build it." in result

    def test_render_with_iteration(self) -> None:
        renderer = PromptTemplateRenderer()
        spec = Spec(frontmatter=SpecFrontmatter(id="001-test"), content="")
        template = "{% for item in context.artifacts %}{{ item }}\n{% endfor %}"
        result = renderer.render_string(template, spec, context={"artifacts": ["a", "b", "c"]})
        assert "a" in result
        assert "b" in result
        assert "c" in result
