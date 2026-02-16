"""Tests for the document production plugin."""

from __future__ import annotations

from pathlib import Path

import pytest

from vizier.core.models.spec import Spec, SpecComplexity, SpecFrontmatter, SpecStatus
from vizier.core.plugins.base_plugin import BasePlugin
from vizier.core.plugins.base_quality_gate import BaseQualityGate
from vizier.core.plugins.base_worker import BaseWorker
from vizier.core.plugins.criteria_loader import CriteriaLibraryLoader
from vizier.core.plugins.discovery import clear_registry, discover_plugins, register_plugin
from vizier.plugins.documents.plugin import (
    ARCHITECT_GUIDE,
    QUALITY_GATE_PROMPT,
    WORKER_PROMPT,
    DocumentReviewer,
    DocumentsPlugin,
    DocumentWriter,
)


@pytest.fixture()
def plugin() -> DocumentsPlugin:
    return DocumentsPlugin()


@pytest.fixture()
def worker() -> DocumentWriter:
    return DocumentWriter()


@pytest.fixture()
def quality_gate() -> DocumentReviewer:
    return DocumentReviewer()


@pytest.fixture()
def sample_spec() -> Spec:
    return Spec(
        frontmatter=SpecFrontmatter(
            id="042-write-report",
            status=SpecStatus.READY,
            priority=2,
            complexity=SpecComplexity.MEDIUM,
            plugin="documents",
        ),
        content="Write a quarterly performance report with executive summary.",
    )


@pytest.fixture()
def high_priority_spec() -> Spec:
    return Spec(
        frontmatter=SpecFrontmatter(
            id="001-urgent-memo",
            status=SpecStatus.IN_PROGRESS,
            priority=1,
            complexity=SpecComplexity.HIGH,
            plugin="documents",
        ),
        content="Draft an urgent security incident memo for leadership.",
    )


class TestDocumentsPlugin:
    def test_is_base_plugin(self, plugin: DocumentsPlugin) -> None:
        assert isinstance(plugin, BasePlugin)

    def test_name(self, plugin: DocumentsPlugin) -> None:
        assert plugin.name == "documents"

    def test_description(self, plugin: DocumentsPlugin) -> None:
        assert plugin.description != ""
        assert "document" in plugin.description.lower()

    def test_worker_class(self, plugin: DocumentsPlugin) -> None:
        assert plugin.worker_class is DocumentWriter

    def test_quality_gate_class(self, plugin: DocumentsPlugin) -> None:
        assert plugin.quality_gate_class is DocumentReviewer

    def test_default_model_tiers(self, plugin: DocumentsPlugin) -> None:
        tiers = plugin.default_model_tiers
        assert tiers["worker"] == "sonnet"
        assert tiers["quality_gate"] == "sonnet"
        assert tiers["architect"] == "opus"

    def test_architect_guide_not_empty(self, plugin: DocumentsPlugin) -> None:
        guide = plugin.get_architect_guide()
        assert len(guide) > 0
        assert guide == ARCHITECT_GUIDE

    def test_architect_guide_has_decomposition_patterns(self, plugin: DocumentsPlugin) -> None:
        guide = plugin.get_architect_guide()
        assert "Report" in guide
        assert "Proposal" in guide
        assert "Memo" in guide

    def test_architect_guide_has_complexity_guidelines(self, plugin: DocumentsPlugin) -> None:
        guide = plugin.get_architect_guide()
        assert "Low" in guide
        assert "Medium" in guide
        assert "High" in guide

    def test_criteria_library_loaded_from_files(self, plugin: DocumentsPlugin) -> None:
        library = plugin.get_criteria_library()
        assert len(library) == 3
        assert all(len(v) > 0 for v in library.values())

    def test_criteria_library_has_all_entries(self, plugin: DocumentsPlugin) -> None:
        library = plugin.get_criteria_library()
        expected_keys = {"structure_complete", "facts_sourced", "formatting_standards"}
        assert set(library.keys()) == expected_keys

    def test_criteria_values_are_nonempty(self, plugin: DocumentsPlugin) -> None:
        library = plugin.get_criteria_library()
        for key, value in library.items():
            assert len(value) > 0, f"Criteria '{key}' has empty definition"

    def test_programmatic_registration(self, plugin: DocumentsPlugin) -> None:
        register_plugin("documents", DocumentsPlugin)
        plugins = discover_plugins()
        assert "documents" in plugins
        assert plugins["documents"].name == "documents"
        clear_registry()

    def test_description_mentions_quality(self, plugin: DocumentsPlugin) -> None:
        assert "quality" in plugin.description.lower() or "review" in plugin.description.lower()


class TestDocumentWriter:
    def test_is_base_worker(self, worker: DocumentWriter) -> None:
        assert isinstance(worker, BaseWorker)

    def test_allowed_tools(self, worker: DocumentWriter) -> None:
        tools = worker.allowed_tools
        assert "file_read" in tools
        assert "file_write" in tools
        assert "web_search" in tools

    def test_no_bash_tool(self, worker: DocumentWriter) -> None:
        assert "bash" not in worker.allowed_tools

    def test_no_git_tool(self, worker: DocumentWriter) -> None:
        assert "git" not in worker.allowed_tools

    def test_tool_restrictions_empty(self, worker: DocumentWriter) -> None:
        assert worker.tool_restrictions == {}

    def test_git_strategy(self, worker: DocumentWriter) -> None:
        assert worker.git_strategy == "commit_to_main"

    def test_get_prompt_includes_spec_id(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "042-write-report" in prompt

    def test_get_prompt_includes_priority(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "2" in prompt

    def test_get_prompt_includes_complexity(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "medium" in prompt

    def test_get_prompt_includes_content(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "quarterly performance report" in prompt

    def test_get_prompt_includes_constitution(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        context = {"constitution": "Follow the company style guide"}
        prompt = worker.get_prompt(sample_spec, context)
        assert "company style guide" in prompt

    def test_get_prompt_includes_learnings(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        context = {"learnings": "Previous reports lacked executive summaries"}
        prompt = worker.get_prompt(sample_spec, context)
        assert "lacked executive summaries" in prompt

    def test_get_prompt_default_constitution(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "No project constitution available" in prompt

    def test_get_prompt_default_learnings(self, worker: DocumentWriter, sample_spec: Spec) -> None:
        prompt = worker.get_prompt(sample_spec, {})
        assert "No learnings available" in prompt

    def test_get_prompt_with_high_priority_spec(self, worker: DocumentWriter, high_priority_spec: Spec) -> None:
        prompt = worker.get_prompt(high_priority_spec, {})
        assert "001-urgent-memo" in prompt
        assert "high" in prompt
        assert "security incident memo" in prompt


class TestDocumentReviewer:
    def test_is_base_quality_gate(self, quality_gate: DocumentReviewer) -> None:
        assert isinstance(quality_gate, BaseQualityGate)

    def test_automated_checks(self, quality_gate: DocumentReviewer) -> None:
        checks = quality_gate.automated_checks
        assert len(checks) == 2
        names = [c["name"] for c in checks]
        assert "output_exists" in names
        assert "no_placeholders" in names

    def test_automated_checks_have_commands(self, quality_gate: DocumentReviewer) -> None:
        for check in quality_gate.automated_checks:
            assert "command" in check
            assert len(check["command"]) > 0

    def test_automated_checks_commands(self, quality_gate: DocumentReviewer) -> None:
        checks = {c["name"]: c["command"] for c in quality_gate.automated_checks}
        assert "ls" in checks["output_exists"]
        assert "grep" in checks["no_placeholders"]

    def test_get_prompt_includes_spec_id(self, quality_gate: DocumentReviewer, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff here", {})
        assert "042-write-report" in prompt

    def test_get_prompt_includes_diff(self, quality_gate: DocumentReviewer, sample_spec: Spec) -> None:
        diff = "+## Executive Summary\n+Revenue grew 15% year-over-year."
        prompt = quality_gate.get_prompt(sample_spec, diff, {})
        assert "Executive Summary" in prompt

    def test_get_prompt_empty_diff(self, quality_gate: DocumentReviewer, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "", {})
        assert "No diff available" in prompt

    def test_get_prompt_includes_content(self, quality_gate: DocumentReviewer, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff", {})
        assert "quarterly performance report" in prompt

    def test_get_prompt_includes_complexity(self, quality_gate: DocumentReviewer, sample_spec: Spec) -> None:
        prompt = quality_gate.get_prompt(sample_spec, "diff", {})
        assert "medium" in prompt


class TestCriteriaFiles:
    def test_criteria_directory_exists(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        assert criteria_dir.exists()
        assert criteria_dir.is_dir()

    def test_all_criteria_files_exist(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        expected = {
            "structure_complete.md",
            "facts_sourced.md",
            "formatting_standards.md",
        }
        actual = {f.name for f in criteria_dir.glob("*.md")}
        assert actual == expected

    def test_criteria_files_are_nonempty(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        for md_file in criteria_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8").strip()
            assert len(content) > 0, f"{md_file.name} is empty"

    def test_criteria_loader_loads_all(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        library = loader.load()
        assert len(library) == 3
        assert "structure_complete" in library
        assert "facts_sourced" in library
        assert "formatting_standards" in library

    def test_criteria_loader_get_single(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        content = loader.get("structure_complete")
        assert content is not None
        assert "section" in content.lower()

    def test_criteria_loader_get_missing(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        loader = CriteriaLibraryLoader(criteria_dir)
        assert loader.get("nonexistent") is None

    def test_criteria_library_keys_match_files(self) -> None:
        criteria_dir = Path(__file__).parent.parent / "vizier" / "plugins" / "documents" / "criteria"
        file_keys = {f.stem for f in criteria_dir.glob("*.md")}
        plugin = DocumentsPlugin()
        library_keys = set(plugin.get_criteria_library().keys())
        assert library_keys == file_keys


class TestPromptTemplates:
    def test_worker_prompt_has_placeholders(self) -> None:
        assert "{spec_id}" in WORKER_PROMPT
        assert "{priority}" in WORKER_PROMPT
        assert "{complexity}" in WORKER_PROMPT
        assert "{content}" in WORKER_PROMPT
        assert "{constitution}" in WORKER_PROMPT
        assert "{learnings}" in WORKER_PROMPT

    def test_worker_prompt_has_document_instructions(self) -> None:
        assert "Read the source materials" in WORKER_PROMPT
        assert "document structure" in WORKER_PROMPT
        assert "Cite sources" in WORKER_PROMPT

    def test_quality_gate_prompt_has_placeholders(self) -> None:
        assert "{spec_id}" in QUALITY_GATE_PROMPT
        assert "{complexity}" in QUALITY_GATE_PROMPT
        assert "{content}" in QUALITY_GATE_PROMPT
        assert "{diff}" in QUALITY_GATE_PROMPT

    def test_quality_gate_prompt_has_evaluation_criteria(self) -> None:
        assert "Structure" in QUALITY_GATE_PROMPT
        assert "Content completeness" in QUALITY_GATE_PROMPT
        assert "Factual accuracy" in QUALITY_GATE_PROMPT
        assert "Formatting" in QUALITY_GATE_PROMPT

    def test_quality_gate_prompt_has_verdict(self) -> None:
        assert "PASS" in QUALITY_GATE_PROMPT
        assert "FAIL" in QUALITY_GATE_PROMPT

    def test_architect_guide_has_sub_spec_format(self) -> None:
        assert "Sub-Spec Format" in ARCHITECT_GUIDE
        assert "acceptance criteria" in ARCHITECT_GUIDE.lower()

    def test_worker_prompt_no_software_terms(self) -> None:
        assert "codebase" not in WORKER_PROMPT.lower()
        assert "Write clean, well-typed code" not in WORKER_PROMPT

    def test_quality_gate_no_software_terms(self) -> None:
        assert "Test coverage" not in QUALITY_GATE_PROMPT
        assert "Edge cases" not in QUALITY_GATE_PROMPT
