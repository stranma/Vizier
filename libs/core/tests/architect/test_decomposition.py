"""Tests for Architect decomposition logic."""

from __future__ import annotations

from vizier.core.architect.decomposition import (
    SubSpecDefinition,
    estimate_complexity,
    generate_sub_spec_id,
    parse_decomposition,
)


class TestParseDecomposition:
    def test_parses_single_sub_spec(self) -> None:
        response = (
            "Here is the decomposition:\n\n"
            "## Sub-spec: Create data model\n"
            "Complexity: low\n"
            "Priority: 1\n"
            "Artifacts: src/models.py\n\n"
            "Create the User data model with id, name, and email fields.\n\n"
            "@criteria/file_exists\n"
        )
        specs = parse_decomposition(response)
        assert len(specs) == 1
        assert specs[0].title == "Create data model"
        assert specs[0].complexity == "low"
        assert specs[0].priority == 1
        assert specs[0].artifacts == ["src/models.py"]
        assert "file_exists" in specs[0].criteria_refs

    def test_parses_multiple_sub_specs(self) -> None:
        response = (
            "## Sub-spec: Create data model\n"
            "Complexity: low\n"
            "Priority: 1\n"
            "Artifacts: src/models.py\n\n"
            "Create the data model.\n\n"
            "## Sub-spec: Add API endpoint\n"
            "Complexity: medium\n"
            "Priority: 2\n"
            "Artifacts: src/api.py, src/routes.py\n\n"
            "Create the API endpoint for CRUD operations.\n"
        )
        specs = parse_decomposition(response)
        assert len(specs) == 2
        assert specs[0].title == "Create data model"
        assert specs[1].title == "Add API endpoint"
        assert specs[1].artifacts == ["src/api.py", "src/routes.py"]

    def test_defaults_when_fields_missing(self) -> None:
        response = "## Sub-spec: Simple task\n\nJust do it.\n"
        specs = parse_decomposition(response)
        assert len(specs) == 1
        assert specs[0].complexity == "medium"
        assert specs[0].priority == 1
        assert specs[0].artifacts == []

    def test_empty_response_returns_empty(self) -> None:
        assert parse_decomposition("") == []
        assert parse_decomposition("No sub-specs here.") == []

    def test_extracts_multiple_criteria_refs(self) -> None:
        response = (
            "## Sub-spec: Full feature\n\n"
            "Build the feature.\n\n"
            "@criteria/tests_pass and @criteria/lint_clean must hold.\n"
        )
        specs = parse_decomposition(response)
        assert len(specs) == 1
        assert "tests_pass" in specs[0].criteria_refs
        assert "lint_clean" in specs[0].criteria_refs

    def test_case_insensitive_fields(self) -> None:
        response = "## Sub-spec: Test task\ncomplexity: HIGH\npriority: 3\nartifacts: file.py\n\nDescription here.\n"
        specs = parse_decomposition(response)
        assert len(specs) == 1
        assert specs[0].complexity == "high"
        assert specs[0].priority == 3


class TestEstimateComplexity:
    def test_low_complexity(self) -> None:
        assert estimate_complexity("short task", 0, 0) == "low"

    def test_medium_complexity(self) -> None:
        desc = " ".join(["word"] * 120)
        assert estimate_complexity(desc, 1, 1) == "medium"

    def test_high_complexity(self) -> None:
        desc = " ".join(["word"] * 250)
        assert estimate_complexity(desc, 3, 3) == "high"

    def test_criteria_and_artifacts_add_score(self) -> None:
        assert estimate_complexity("simple", 4, 4) == "high"


class TestGenerateSubSpecId:
    def test_basic_id(self) -> None:
        result = generate_sub_spec_id("001-add-auth", 1, "Create data model")
        assert result == "001-add-auth-01-create-data-model"

    def test_slug_truncation(self) -> None:
        result = generate_sub_spec_id(
            "001-task", 2, "A very long title that should be truncated to thirty characters max"
        )
        assert len(result.split("-", 2)[2]) <= 40

    def test_special_characters_removed(self) -> None:
        result = generate_sub_spec_id("001-task", 1, "Fix bug (critical!)")
        assert "(" not in result
        assert "!" not in result

    def test_empty_title_fallback(self) -> None:
        result = generate_sub_spec_id("001-task", 1, "!!!")
        assert result == "001-task-01-subtask"


class TestSubSpecDefinition:
    def test_model_creation(self) -> None:
        defn = SubSpecDefinition(
            title="Test",
            description="Test description",
            complexity="high",
            priority=2,
            artifacts=["file.py"],
            criteria_refs=["tests_pass"],
        )
        assert defn.title == "Test"
        assert defn.complexity == "high"
        assert defn.priority == 2
