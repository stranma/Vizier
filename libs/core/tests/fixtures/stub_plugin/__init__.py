"""Stub plugin for Phase 2 testing (D35, D39).

Minimal plugin that exercises all base class features:
- StubWorker: file_read + file_write tools, commit_to_main git strategy
- StubQualityGate: checks that artifact file exists and is non-empty
- One criterion: @criteria/file_exists
- Prompt templates for worker and quality gate

Registered programmatically in tests (not via entry points).
"""

from vizier.core.models.spec import Spec
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker


class StubWorker(BaseWorker):
    """Test worker that creates/modifies a simple text file per spec."""

    @property
    def allowed_tools(self) -> list[str]:
        return ["file_read", "file_write"]

    @property
    def tool_restrictions(self) -> dict[str, dict[str, list[str]]]:
        return {}

    @property
    def git_strategy(self) -> str:
        return "commit_to_main"

    def get_prompt(self, spec: Spec, context: dict) -> str:
        return (
            f"You are a stub worker. Implement the following spec:\n\n"
            f"Spec ID: {spec.frontmatter.id}\n"
            f"Priority: {spec.frontmatter.priority}\n"
            f"Complexity: {spec.frontmatter.complexity}\n\n"
            f"Instructions:\n{spec.content}\n\n"
            f"Project constitution: {context.get('constitution', 'N/A')}\n"
            f"Learnings: {context.get('learnings', 'N/A')}\n"
        )


class StubQualityGate(BaseQualityGate):
    """Test quality gate that checks artifact file exists and is non-empty."""

    @property
    def automated_checks(self) -> list[dict[str, str]]:
        return [
            {"name": "file_exists", "command": "test -f {artifact}"},
        ]

    def get_prompt(self, spec: Spec, diff: str, context: dict) -> str:
        return (
            f"You are a stub quality gate. Review the following spec:\n\n"
            f"Spec ID: {spec.frontmatter.id}\n\n"
            f"Diff:\n{diff}\n\n"
            f"Acceptance criteria from spec:\n{spec.content}\n\n"
            f"Evaluate whether the implementation meets all criteria.\n"
            f"Respond with PASS or FAIL and detailed feedback.\n"
        )


class StubPlugin(BasePlugin):
    """Minimal test plugin exercising all BasePlugin features."""

    @property
    def name(self) -> str:
        return "test-stub"

    @property
    def description(self) -> str:
        return "Stub plugin for testing the inner loop"

    @property
    def worker_class(self) -> type[BaseWorker]:
        return StubWorker

    @property
    def quality_gate_class(self) -> type[BaseQualityGate]:
        return StubQualityGate

    @property
    def default_model_tiers(self) -> dict[str, str]:
        return {
            "worker": "haiku",
            "quality_gate": "haiku",
            "architect": "opus",
        }

    def get_architect_guide(self) -> str:
        return "Decompose tasks into simple file creation sub-tasks."

    def get_criteria_library(self) -> dict[str, str]:
        return {
            "file_exists": "The artifact file must exist and be non-empty.",
        }
