"""Tests for the software development plugin."""

from __future__ import annotations

from pathlib import Path

import pytest

from vizier.core.models.spec import Spec, SpecComplexity, SpecFrontmatter, SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.criteria_loader import CriteriaLibraryLoader
from vizier.core.plugins.discovery import clear_registry, discover_plugins, register_plugin
from vizier.plugins.software.plugin import (
    ARCHITECT_GUIDE,
    QUALITY_GATE_PROMPT,
    WORKER_PROMPT,
    SoftwareCoder,
    SoftwarePlugin,
    SoftwareQualityGate,
)


@pytest.fixture()
def plugin() -> SoftwarePlugin:
    return SoftwarePlugin()


@pytest.fixture()
def worker() -> SoftwareCoder:
    return SoftwareCoder()


@pytest.fixture()
def quality_gate() -> SoftwareQualityGate:
    return SoftwareQualityGate()


@pytest.fixture()
def sample_spec() -> Spec:
    return Spec(
        frontmatter=SpecFrontmatter(
            id="042-add-login",
            status=SpecStatus.READY,
            priority=2,
            complexity=SpecComplexity.MEDIUM,
            plugin="software",
        ),
        content="Add a login form with email and password fields.",
    )


@pytest.fixture()
def high_priority_spec() -> Spec:
    return Spec(
        frontmatter=SpecFrontmatter(
            id="001-critical-fix",
            status=SpecStatus.IN_PROGRESS,
            priority=1,
            complexity=SpecComplexity.HIGH,
            plugin="software",
        ),
        content="Fix the authentication bypass vulnerability in /api/admin.",
    )


class TestSoftwarePlugin:
    def test_is_base_plugin(self, plugin: SoftwarePlugin) -> None:
        assert isinstance(plugin, BasePlugin)

    def test_name(self, plugin: SoftwarePlugin) -> None:
        assert plugin.name == "software"

    def test_description(self, plugin: SoftwarePlugin) -> None:
        assert plugin.description != ""
        assert "software" in plugin.description.lower()

    def test_worker_class(self, plugin: SoftwarePlugin) -> None:
        assert plugin.worker_class is SoftwareCoder

    def test_quality_gate_class(self, plugin: SoftwarePlugin) -> None:
        assert plugin.quality_gate_class is SoftwareQualityGate

    def test_default_model_tiers(self, plugin: SoftwarePlugin) -> None:
        tiers = plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["quality_gate"] == "sonnet"
        assert tiers["architect"] == "opus"

    def test_architect_guide_not_empty(self, plugin: SoftwarePlugin) -> None:
        guide = plugin.get_architect_guide()
        assert len(guide) > 0
        assert guide == ARCHITECT_GUIDE

    def test_architect_guide_has_decomposition_patterns(self, plugin: SoftwarePlugin) -> None:
        guide = plugin.get_architect_guide()
        assert "Feature Implementation" in guide
        assert "Bug Fix" in guide
        assert "Refactoring" in guide

    def test_architect_guide_has_complexity_guidelines(self, plugin: SoftwarePlugin) -> None:
        guide = plugin.get_architect_guide()
        assert "Low" in guide
        assert "Medium" in guide
        assert "High" in guide

    def test_criteria_library_loaded_from_files(self, plugin: SoftwarePlugin) -> None:
        library = plugin.get_criteria_library()
        assert len(library) == 5
        assert all(len(v) > 0 for v in library.values())

    def test_criteria_library_has_all_entries(self, plugin: SoftwarePlugin) -> None:
        library = plugin.get_criteria_library()
        expected_keys = {"tests_pass", "lint_clean", "type_check", "no_debug_artifacts", "test_meaningfulness"}
        assert set(library.keys()) == expected_keys

    def test_criteria_values_are_nonempty(self, plugin: SoftwarePlugin) -> None:
        library = plugin.get_criteria_library()
        for key, value in library.items():
            assert len(value) > 0, f"Criteria '{key}' has empty definition"

    def test_programmatic_registration(self, plugin: SoftwarePlugin) -> None:
        register_plugin("software", SoftwarePlugin)
        plugins = discover_plugins()
        assert "software" in plugins
        assert plugins["software"].name == "software"
        clear_registry()


class TestSoftwareCoder:
    def test_is_base_worker(self, worker: SoftwareCoder) -> None:
        assert isinstance(worker, BaseWorker)

    def test_allowed_tools(self, worker: SoftwareCoder) -> None:
        tools = worker.allowed_tools
        assert "file_read" in tools
        assert "file_write" in tools
        assert "bash" in tools
        assert "git" in tools

    def test_tool_restrictions_bash(self, worker: SoftwareCoder) -> None:
        restrictions = worker.tool_restrictions
        assert "bash" in restrictions
        assert "denied_patterns" in restrictions["bash"]
        patterns = restrictions["bash"]["denied_patterns"]
        assert any("rm" in p for p in patterns)
        assert any("sudo" in p for p in patterns)

    def test_tool_restrictions_git(self, worker: SoftwareCoder) -> None:
        import re

        restrictions = worker.tool_restrictions
        assert "git" in restrictions
        assert "denied_patterns" in restrictions["git"]
        patterns = [re.compile(p) for p in restrictions["git"]["denied_patterns"]]

        should_deny = [
            "push --force origin main",
            "push -f origin main",
            "reset --hard HEAD~3",
            "clean -fd",
            "clean",
            "config user.email foo@bar.com",
            "init",
            "restore src/main.py",
            "restore --staged file.py",
            "rebase -i HEAD~5",
            "branch -D feature/old",
            "checkout .",
        ]
        for cmd in should_deny:
            matched = any(p.search(cmd) for p in patterns)
            assert matched, f"'{cmd}' should be denied by git tool_restrictions"

        should_allow = [
            "push origin main",
            "commit -m 'test'",
            "add .",
            "status",
            "diff HEAD",
            "log --oneline",
            "branch -a",
            "stash push -m 'wip'",
            "fetch origin",
            "pull origin main",
        ]
        for cmd in should_allow:
            matched = any(p.search(cmd) for p in patterns)
            assert not matched, f"'{cmd}' should NOT be denied by git tool_restrictions"

    def test_git_strategy(self, worker: SoftwareCoder) -> None:
        assert worker.git_strategy == "branch_per_spec"

    def test_get_prompt_includes_spec_id(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "042-add-login" in prompt

    def test_get_prompt_includes_priority(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "2" in prompt

    def test_get_prompt_includes_complexity(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "medium" in prompt

    def test_get_prompt_includes_content(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "login form" in prompt

    def test_get_prompt_includes_constitution(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        context = {"constitution": "Follow PEP 8 style guide"}
        prompt = worker.get_prompt(sample_spec, context)
        assert "PEP 8" in prompt

    def test_get_prompt_includes_learnings(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        context = {"learnings": "Previous login form had XSS vulnerability"}
        prompt = worker.get_prompt(sample_spec, context)
        assert "XSS vulnerability" in prompt

    def test_get_prompt_default_constitution(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "No project constitution available" in prompt

    def test_get_prompt_default_learnings(self, worker: SoftwareCoder, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "No learnings available" in prompt

    def test_get_prompt_with_high_priority_spec(self, worker: SoftwareCoder, high_priority_spec: Spec) -> None:
        prompt = worker.get_prompt(high_priority_spec, {})
        assert "001-critical-fix" in prompt
        assert "high" in prompt
        assert "authentication bypass" in prompt


class TestSoftwareQualityGate:
    def test_is_base_quality_gate(self, quality_gate: SoftwareQualityGate) -> None:
        assert isinstance(quality_gate, BaseQualityGate)

    def test_automated_checks(self, quality_gate: SoftwareQualityGate) -> None:
        checks = quality_gate.automated_checks
        assert len(checks) == 3
        names = [c["name"] for c in checks]
        assert "tests_pass" in names
        assert "lint_clean" in names
        assert "type_check" in names

    def test_automated_checks_have_commands(self, quality_gate: SoftwareQualityGate) -> None:
        for check in quality_gate.automated_checks:
            assert "command" in check
            assert len(check["command"]) > 0

    def test_automated_checks_commands(self, quality_gate: SoftwareQualityGate) -> None:
        checks = {c["name"]: c["command"] for c in quality_gate.automated_checks}
        assert "pytest" in checks["tests_pass"]
        assert "ruff" in checks["lint_clean"]
        assert "pyright" in checks["type_check"]

    def test_get_prompt_includes_spec_id(self, quality_gate: SoftwareQualityGate, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff here", {})
        assert "042-add-login" in prompt

    def test_get_prompt_includes_diff(self, quality_gate: SoftwareQualityGate, sample_spec: Spec) -> None:
        diff = "+def login(email, password):\n+    return authenticate(email, password)"
        prompt = quality_gate.get_prompt(sample_spec, diff, {})
        assert "login(email, password)" in prompt

    def test_get_prompt_empty_diff(self, quality_gate: SoftwareQualityGate, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "", {})
        assert "No diff available" in prompt

    def test_get_prompt_includes_content(self, quality_gate: SoftwareQualityGate, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff", {})
        assert "login form" in prompt

    def test_get_prompt_includes_complexity(self, quality_gate: SoftwareQualityGate, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff", {})
        assert "medium" in prompt


class TestCriteriaFiles:
    def test_criteria_directory_exists(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        assert criteria_dir.exists()
        assert criteria_dir.is_dir()

    def test_all_criteria_files_exist(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        expected = {
            "tests_pass.md",
            "lint_clean.md",
            "type_check.md",
            "no_debug_artifacts.md",
            "test_meaningfulness.md",
        }
        actual = {f.name for f in criteria_dir.glob("*.md")}
        assert actual == expected

    def test_criteria_files_are_nonempty(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        for md_file in criteria_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8").strip()
            assert len(content) > 0, f"{md_file.name} is empty"

    def test_criteria_loader_loads_all(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        library = loader.load()
        assert len(library) == 5
        assert "tests_pass" in library
        assert "lint_clean" in library
        assert "type_check" in library
        assert "no_debug_artifacts" in library
        assert "test_meaningfulness" in library

    def test_criteria_loader_get_single(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        content = loader.get("tests_pass")
        assert content is not None
        assert "tests" in content.lower()

    def test_criteria_loader_get_missing(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        assert loader.get("nonexistent") is None


class TestPromptTemplates:
    def test_worker_prompt_has_placeholders(self) -> None:
        assert "{spec_id}" in WORKER_PROMPT
        assert "{priority}" in WORKER_PROMPT
        assert "{complexity}" in WORKER_PROMPT
        assert "{content}" in WORKER_PROMPT
        assert "{constitution}" in WORKER_PROMPT
        assert "{learnings}" in WORKER_PROMPT

    def test_worker_prompt_has_instructions(self) -> None:
        assert "Read the relevant source files" in WORKER_PROMPT
        assert "Write clean" in WORKER_PROMPT
        assert "tests" in WORKER_PROMPT.lower()

    def test_quality_gate_prompt_has_placeholders(self) -> None:
        assert "{spec_id}" in QUALITY_GATE_PROMPT
        assert "{complexity}" in QUALITY_GATE_PROMPT
        assert "{content}" in QUALITY_GATE_PROMPT
        assert "{diff}" in QUALITY_GATE_PROMPT

    def test_quality_gate_prompt_has_evaluation_criteria(self) -> None:
        assert "Correctness" in QUALITY_GATE_PROMPT
        assert "Test coverage" in QUALITY_GATE_PROMPT
        assert "Code quality" in QUALITY_GATE_PROMPT
        assert "Edge cases" in QUALITY_GATE_PROMPT

    def test_quality_gate_prompt_has_verdict(self) -> None:
        assert "PASS" in QUALITY_GATE_PROMPT
        assert "FAIL" in QUALITY_GATE_PROMPT

    def test_architect_guide_has_sub_spec_format(self) -> None:
        assert "Sub-Spec Format" in ARCHITECT_GUIDE
        assert "acceptance criteria" in ARCHITECT_GUIDE.lower()

    def test_criteria_library_keys_match_files(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "software" / "criteria"
        file_keys = {f.stem for f in criteria_dir.glob("*.md")}
        plugin = SoftwarePlugin()
        library_keys = set(plugin.get_criteria_library().keys())
        assert library_keys == file_keys
