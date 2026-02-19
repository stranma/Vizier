"""Tests for project capability summary (D59)."""

from vizier.core.agents.ea.capability_summary import (
    PLUGIN_DEFAULTS,
    ProjectCapability,
    build_capability,
    format_capabilities_for_prompt,
)


class TestProjectCapability:
    def test_defaults(self) -> None:
        cap = ProjectCapability(name="test-project")
        assert cap.name == "test-project"
        assert cap.plugin == "software"
        assert cap.ci_signals == []
        assert cap.autonomy_stage == "supervised"

    def test_custom_values(self) -> None:
        cap = ProjectCapability(
            name="alpha",
            plugin="documents",
            ci_signals=["link_check"],
            done_definition="All links valid",
            critical_tools=["read_file"],
            autonomy_stage="autonomous",
        )
        assert cap.plugin == "documents"
        assert cap.ci_signals == ["link_check"]
        assert cap.autonomy_stage == "autonomous"


class TestBuildCapability:
    def test_software_defaults(self) -> None:
        cap = build_capability(name="alpha", plugin="software")
        assert cap.ci_signals == PLUGIN_DEFAULTS["software"]["ci_signals"]
        assert cap.done_definition == PLUGIN_DEFAULTS["software"]["done_definition"]
        assert cap.critical_tools == PLUGIN_DEFAULTS["software"]["critical_tools"]

    def test_documents_defaults(self) -> None:
        cap = build_capability(name="beta", plugin="documents")
        assert cap.ci_signals == PLUGIN_DEFAULTS["documents"]["ci_signals"]

    def test_unknown_plugin(self) -> None:
        cap = build_capability(name="gamma", plugin="custom")
        assert cap.ci_signals == []
        assert cap.done_definition == ""

    def test_overrides(self) -> None:
        cap = build_capability(
            name="alpha",
            plugin="software",
            overrides={"ci_signals": ["custom_test"], "done_definition": "Custom done"},
        )
        assert cap.ci_signals == ["custom_test"]
        assert cap.done_definition == "Custom done"

    def test_autonomy_stage(self) -> None:
        cap = build_capability(name="alpha", autonomy_stage="autonomous")
        assert cap.autonomy_stage == "autonomous"


class TestFormatCapabilities:
    def test_empty_list(self) -> None:
        result = format_capabilities_for_prompt([])
        assert result == "No projects registered."

    def test_single_project(self) -> None:
        caps = [build_capability(name="alpha", plugin="software")]
        result = format_capabilities_for_prompt(caps)
        assert "### alpha" in result
        assert "Plugin: software" in result
        assert "pytest" in result
        assert "Autonomy: supervised" in result

    def test_multiple_projects(self) -> None:
        caps = [
            build_capability(name="alpha", plugin="software"),
            build_capability(name="beta", plugin="documents"),
        ]
        result = format_capabilities_for_prompt(caps)
        assert "### alpha" in result
        assert "### beta" in result
        assert "Plugin: software" in result
        assert "Plugin: documents" in result

    def test_missing_optional_fields(self) -> None:
        cap = ProjectCapability(name="minimal")
        result = format_capabilities_for_prompt([cap])
        assert "### minimal" in result
        assert "Plugin: software" in result
