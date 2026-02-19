"""Document production plugin for Vizier.

Defines write-set patterns, required evidence types, system prompt guides,
and criteria library for document production projects.
"""

from __future__ import annotations

from vizier.core.plugins.base_plugin import BasePlugin


class DocumentsPlugin(BasePlugin):
    """Plugin for document production projects.

    Provides write-set patterns for docs and templates, requires
    link-check/structure/preview evidence, and includes role-specific
    system prompt guides for Scout, Architect, Worker, and Quality Gate.
    """

    @property
    def name(self) -> str:
        return "documents"

    @property
    def description(self) -> str:
        return "Document production plugin: docs, templates, assets"

    @property
    def worker_write_set(self) -> list[str]:
        return [
            "docs/**",
            "templates/**",
            "assets/**",
            "*.md",
            "*.rst",
            "*.txt",
        ]

    @property
    def required_evidence(self) -> list[str]:
        return [
            "link_check_output",
            "structure_validation",
            "rendered_preview_path",
        ]

    @property
    def system_prompts(self) -> dict[str, str]:
        return {
            "scout": SCOUT_GUIDE,
            "architect": ARCHITECT_GUIDE,
            "worker": WORKER_GUIDE,
            "quality_gate": QUALITY_GATE_GUIDE,
        }

    @property
    def tool_overrides(self) -> dict[str, dict[str, list[str]]]:
        return {
            "bash": {
                "denied_patterns": [
                    r"rm\s+-rf\s+/",
                ],
            },
        }


SCOUT_GUIDE = """\
Research document standards and templates:
- Check for existing templates in the project
- Look for style guides or brand guidelines
- Research format requirements (Markdown, RST, DOCX)
- Identify any compliance or regulatory requirements
"""

ARCHITECT_GUIDE = """\
Decompose documents by section/chapter:
1. Outline and structure first (table of contents)
2. Individual sections as separate sub-specs
3. Cross-references and links last (depends on all sections)
4. Final review and formatting (depends on all above)

Each sub-spec should:
- Target one section or closely related group
- Include word count or page estimates
- Declare write-set scoped to specific files
"""

WORKER_GUIDE = """\
Writing workflow:
1. Read existing content and style guides
2. Draft content following templates
3. Check formatting and structure
4. Verify all links and references

Quality expectations:
- Clear, concise language
- Consistent formatting and style
- All links valid
- Proper heading hierarchy
"""

QUALITY_GATE_GUIDE = """\
Document quality checks:
1. Link validation: all internal and external links resolve
2. Structure validation: proper heading hierarchy, no orphan sections
3. Rendered preview: document renders correctly in target format

Semantic checks (LLM-assisted):
- Content matches spec requirements
- Language is clear and professional
- No placeholder text or TODO markers
- Consistent terminology throughout
"""
