"""Jinja2 prompt template renderer for plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

import jinja2

if TYPE_CHECKING:
    from pathlib import Path

    from vizier.core.models.spec import Spec


class PromptTemplateRenderer:
    """Renders Jinja2 prompt templates with spec and context data.

    :param template_dir: Directory containing .md Jinja2 templates.
    """

    def __init__(self, template_dir: str | Path | None = None) -> None:
        if template_dir is not None:
            self._env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(str(template_dir)),
                undefined=jinja2.StrictUndefined,
                keep_trailing_newline=True,
            )
        else:
            self._env = jinja2.Environment(
                loader=jinja2.BaseLoader(),
                undefined=jinja2.StrictUndefined,
                keep_trailing_newline=True,
            )

    def render_file(self, template_name: str, spec: Spec, context: dict | None = None) -> str:
        """Render a template file with spec and context data.

        :param template_name: Template filename (e.g. "worker.md").
        :param spec: The spec to inject.
        :param context: Additional context variables.
        :returns: Rendered template string.
        """
        template = self._env.get_template(template_name)
        return template.render(
            spec=spec.frontmatter,
            content=spec.content,
            context=context or {},
            **self._extract_spec_vars(spec),
        )

    def render_string(self, template_str: str, spec: Spec, context: dict | None = None) -> str:
        """Render a template string with spec and context data.

        :param template_str: Jinja2 template as a string.
        :param spec: The spec to inject.
        :param context: Additional context variables.
        :returns: Rendered template string.
        """
        template = self._env.from_string(template_str)
        return template.render(
            spec=spec.frontmatter,
            content=spec.content,
            context=context or {},
            **self._extract_spec_vars(spec),
        )

    @staticmethod
    def _extract_spec_vars(spec: Spec) -> dict:
        return {
            "spec_id": spec.frontmatter.id,
            "spec_status": spec.frontmatter.status,
            "spec_complexity": spec.frontmatter.complexity,
            "spec_plugin": spec.frontmatter.plugin,
        }
